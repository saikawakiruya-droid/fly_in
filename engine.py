"""The simulation: drones, the state, the turn rules, observers, the loop.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* Drone, DroneStatus: one drone and where it is.
* SimulationState: the mutable per-turn state of the whole simulation.
* TurnResolver: checks a turn of orders against the rules, then applies it.
* TurnObserver: what the engine calls each turn, and a group of them.
* SimulationEngine: runs the turn loop until every drone is delivered.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from errors import SimulationError, ZoneNotFoundError
from world import Connection, Network, World, Zone, ZoneRole, ZoneType


# --- Drone ------------------------------------------------------------

class DroneStatus(Enum):
    """Lifecycle states of a single drone during the simulation."""

    AT_ZONE = "at_zone"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"


@dataclass
class Drone:
    """A single drone being routed from the start zone to the end zone.

    Attributes:
        drone_id: Unique numeric identifier (rendered as D<drone_id>).
        current_zone: Name of the zone the drone currently occupies, or None
            while mid-transit through a restricted connection.
        status: Current lifecycle state. The simulation starts every drone
            as AT_ZONE in the start zone.
        in_transit_connection: Name of the connection being traversed, set
            only while status is IN_TRANSIT.
        transit_target: Name of the zone the drone will arrive at, set only
            while status is IN_TRANSIT.
    """

    drone_id: int
    current_zone: str | None
    status: DroneStatus = DroneStatus.AT_ZONE
    in_transit_connection: str | None = None
    transit_target: str | None = None

    @property
    def is_delivered(self) -> bool:
        """Return whether this drone has reached the end zone."""
        return self.status is DroneStatus.DELIVERED


# --- SimulationState --------------------------------------------------

@dataclass(frozen=True)
class Move:
    """One drone's action during a single turn, as printed in the output.

    Moves are produced by the ``TurnResolver`` (driven by the engine),
    never by the scheduler.

    Attributes:
        drone_id: Which drone moved.
        destination: Target zone name, or the connection name if the drone
            just entered a restricted-zone transit.
        connection_name: Name of the connection the drone departed along,
            or None for a landing (the drone left its connection then). Only
            departures count toward a connection's capacity. The turn log
            and the rule checks do not use it.
    """

    drone_id: int
    destination: str
    connection_name: str | None = None

    @property
    def text(self) -> str:
        """Return the move as printed: ``D<id>-<destination>``."""
        return f"D{self.drone_id}-{self.destination}"


@dataclass(frozen=True)
class MoveOrder:
    """A scheduler's instruction: move one drone into an adjacent zone.

    The scheduler always names the zone to enter, even a restricted one;
    the ``TurnResolver`` turns that into the connection-name output and
    lands the drone on the next turn by itself.

    Attributes:
        drone_id: Which drone to move.
        zone_name: Name of the adjacent zone the drone should enter.
    """

    drone_id: int
    zone_name: str


class SimulationState:
    """Where every drone is, and how full every zone is, between turns.

    ``load`` counts the drones currently in a zone plus the drones in
    flight toward it (``reserved``), which is what the views display. The
    rules count a drone in flight in its zone only from the turn it lands;
    the scheduler makes sure it will have room then (see ``Scheduler``).

    The mutating methods (``enter_zone``, ``enter_transit``,
    ``complete_transit``) apply one move without checking any rule; the
    ``TurnResolver`` checks a whole turn before calling them.

    Attributes:
        network: The map being simulated (read only).
        turn_number: Number of turns played so far (0 before the first).
        drones: Every drone, delivered or not, keyed by drone_id (1-based).
    """

    def __init__(self, network: Network, nb_drones: int) -> None:
        """Place ``nb_drones`` drones, numbered from 1, in the start zone.

        Args:
            network: The map to simulate.
            nb_drones: Number of drones to create.
        """
        self.network = network
        self.turn_number = 0
        start = network.start_zone.name
        self.drones: dict[int, Drone] = {
            drone_id: Drone(drone_id=drone_id, current_zone=start)
            for drone_id in range(1, nb_drones + 1)
        }
        self._occupancy: dict[str, int] = {start: nb_drones}
        self._reserved: dict[str, int] = {}
        self._link_load: dict[str, int] = {}

    def occupancy(self, zone_name: str) -> int:
        """Return how many undelivered drones are currently in the zone.

        Args:
            zone_name: Name of the zone.

        Returns:
            The number of drones in the zone (0 if none).
        """
        return self._occupancy.get(zone_name, 0)

    def reserved(self, zone_name: str) -> int:
        """Return how many drones in flight will arrive in the zone.

        Args:
            zone_name: Name of the zone.

        Returns:
            The number of drones flying toward the zone (0 if none).
        """
        return self._reserved.get(zone_name, 0)

    def load(self, zone_name: str) -> int:
        """Return occupancy plus reservations: the room already taken.

        Args:
            zone_name: Name of the zone.

        Returns:
            ``occupancy(zone_name) + reserved(zone_name)``.
        """
        return self.occupancy(zone_name) + self.reserved(zone_name)

    def link_load(self, connection: Connection) -> int:
        """Return how many drones are in flight on the connection.

        These drones land at the start of the next turn and leave the
        connection then, so they do not take any of its
        ``max_link_capacity`` during that turn: a connection is used only
        on the turn a drone departs across it.

        Args:
            connection: The connection to look at.

        Returns:
            The number of drones flying along it (0 if none).
        """
        return self._link_load.get(connection.name, 0)

    def active_drones(self) -> list[Drone]:
        """Return the undelivered drones, in drone_id order.

        Returns:
            The drones that have not reached the end zone yet.
        """
        return [d for d in self.drones.values() if not d.is_delivered]

    def drones_in_transit(self) -> list[Drone]:
        """Return the drones in flight toward a restricted zone.

        Returns:
            The drones on a connection, in drone_id order.
        """
        return [
            d for d in self.drones.values()
            if d.status is DroneStatus.IN_TRANSIT
        ]

    @property
    def delivered_count(self) -> int:
        """Return how many drones have reached the end zone."""
        return sum(1 for d in self.drones.values() if d.is_delivered)

    @property
    def is_complete(self) -> bool:
        """Return whether every drone has reached the end zone."""
        return all(d.is_delivered for d in self.drones.values())

    def enter_zone(self, drone_id: int, zone_name: str) -> None:
        """Move a drone standing in a zone straight into another zone.

        Entering the end zone delivers the drone.

        Args:
            drone_id: The drone to move; it must be in a zone.
            zone_name: The zone it enters.
        """
        drone = self._drone_at_zone(drone_id)
        self._leave(drone)
        self._arrive(drone, zone_name)

    def enter_transit(
        self, drone_id: int, connection: Connection, zone_name: str
    ) -> None:
        """Start a two-turn move: the drone leaves its zone for a connection.

        The drone counts in ``reserved(zone_name)`` until it lands on the
        next turn.

        Args:
            drone_id: The drone to move; it must be in a zone.
            connection: The connection it flies along.
            zone_name: The restricted zone it lands in next turn.
        """
        drone = self._drone_at_zone(drone_id)
        self._leave(drone)
        drone.status = DroneStatus.IN_TRANSIT
        drone.in_transit_connection = connection.name
        drone.transit_target = zone_name
        self._add(self._reserved, zone_name, 1)
        self._add(self._link_load, connection.name, 1)

    def complete_transit(self, drone_id: int) -> None:
        """Land a drone in flight in the zone it was flying to.

        Args:
            drone_id: The drone to land.

        Raises:
            SimulationError: If the drone is not in flight.
        """
        drone = self.drones[drone_id]
        target = drone.transit_target
        link = drone.in_transit_connection
        if drone.status is not DroneStatus.IN_TRANSIT or target is None:
            raise SimulationError(f"drone D{drone_id} is not in flight")
        self._add(self._reserved, target, -1)
        if link is not None:
            self._add(self._link_load, link, -1)
        drone.in_transit_connection = None
        drone.transit_target = None
        self._arrive(drone, target)

    def _drone_at_zone(self, drone_id: int) -> Drone:
        """Return a drone that must be standing in a zone.

        Args:
            drone_id: The drone to look up.

        Returns:
            The drone.

        Raises:
            SimulationError: If the drone is not in a zone.
        """
        drone = self.drones[drone_id]
        if drone.status is not DroneStatus.AT_ZONE:
            raise SimulationError(f"drone D{drone_id} is not in a zone")
        return drone

    def _leave(self, drone: Drone) -> None:
        """Take a drone out of its zone's occupancy.

        Args:
            drone: The drone leaving its zone.
        """
        if drone.current_zone is not None:
            self._add(self._occupancy, drone.current_zone, -1)
        drone.current_zone = None

    def _arrive(self, drone: Drone, zone_name: str) -> None:
        """Put a drone in a zone, delivering it if it is the end zone.

        Args:
            drone: The drone arriving.
            zone_name: The zone it arrives in.
        """
        drone.current_zone = zone_name
        if self.network.get_zone(zone_name).role is ZoneRole.END:
            drone.status = DroneStatus.DELIVERED
            return
        drone.status = DroneStatus.AT_ZONE
        self._add(self._occupancy, zone_name, 1)

    @staticmethod
    def _add(counts: dict[str, int], key: str, delta: int) -> None:
        """Add ``delta`` to a count, dropping the key when it reaches 0.

        Args:
            counts: The counts to change.
            key: The zone or connection name.
            delta: The amount to add (negative to subtract).
        """
        value = counts.get(key, 0) + delta
        if value:
            counts[key] = value
        else:
            counts.pop(key, None)


# --- TurnResolver -----------------------------------------------------

@dataclass(frozen=True)
class _Step:
    """One checked move, ready to apply: who goes where, through what."""

    drone: Drone
    connection: Connection
    zone: Zone
    is_arrival: bool


class TurnResolver:
    """Enforces the movement and capacity rules for one simulation turn.

    For every turn it:

    1. lands every drone in flight (a restricted transit must end on the
       turn after it began; no order is needed or accepted for them);
    2. checks each order: known, undelivered, not in flight, at most one
       order per drone, into an existing, non-blocked, adjacent zone other
       than the one the drone is in (waiting means giving no order, so a
       move along a self-loop is rejected);
    3. checks connection capacity: drones departing on the same connection
       must not exceed ``max_link_capacity``. Drones landing this turn leave
       the connection, so they free their slot for departures during the
       same turn (like drones leaving a zone);
    4. checks zone capacity on the final counts, so drones leaving a zone
       free room for drones entering it during the same turn. A drone
       landing in a restricted zone counts in it from this turn on; a drone
       departing toward one does not count in it yet (at the end of the
       turn it is on the connection). A drone that cannot land because its
       zone is full is stuck on the connection, which the rules forbid: it
       is reported as such.

    The resolver does not know the scheduler's planned moves: a plan that
    is not kept shows up as a full zone or a stuck drone.

    Nothing is changed unless the whole turn is legal.
    """

    def __init__(self, network: Network) -> None:
        """Check moves against ``network``.

        Args:
            network: The map whose rules the moves must follow.
        """
        self.network = network

    def resolve(
        self, state: SimulationState, orders: list[MoveOrder]
    ) -> list[Move]:
        """Check and apply one turn, then return its output moves.

        Args:
            state: The state to advance; changed only if the turn is legal.
            orders: The scheduler's orders for drones standing in zones.

        Returns:
            The turn's moves in drone_id order: ``<zone>`` for a completed
            move, ``<connection>`` for a drone that just took off toward a
            restricted zone. Empty if nothing moved.

        Raises:
            SimulationError: If any order breaks a rule, or a drone in
                flight cannot land because its zone is full.
        """
        steps = self._arrivals(state) + self._check_orders(state, orders)
        self._check_links(state, steps)
        self._check_zones(state, steps)
        steps.sort(key=lambda step: step.drone.drone_id)
        moves = [self._apply(state, step) for step in steps]
        state.turn_number += 1
        return moves

    def _arrivals(self, state: SimulationState) -> list[_Step]:
        """Return a landing step for every drone in flight.

        Args:
            state: The state before the turn.

        Returns:
            One arrival step per drone in transit.

        Raises:
            SimulationError: If a drone in flight has no target or
                connection.
        """
        steps: list[_Step] = []
        for drone in state.drones_in_transit():
            link = drone.in_transit_connection
            if drone.transit_target is None or link is None:
                raise SimulationError(
                    f"drone D{drone.drone_id} is in flight without a route"
                )
            zone = self.network.get_zone(drone.transit_target)
            connection = self.network.connection_named(zone.name, link)
            steps.append(_Step(drone, connection, zone, is_arrival=True))
        return steps

    def _check_orders(
        self, state: SimulationState, orders: list[MoveOrder]
    ) -> list[_Step]:
        """Check that each order is for a distinct drone standing in a zone.

        Args:
            state: The state before the turn.
            orders: The scheduler's orders.

        Returns:
            One departure step per order, in order.

        Raises:
            SimulationError: If a drone gets two orders, does not exist,
                is delivered or is in flight, or an order is illegal.
        """
        steps: list[_Step] = []
        ordered: set[int] = set()
        for order in orders:
            label = f"D{order.drone_id}"
            if order.drone_id in ordered:
                raise SimulationError(f"{label} was given two orders")
            ordered.add(order.drone_id)
            drone = state.drones.get(order.drone_id)
            if drone is None:
                raise SimulationError(f"{label} does not exist")
            if drone.status is DroneStatus.DELIVERED:
                raise SimulationError(f"{label} is already delivered")
            if drone.status is not DroneStatus.AT_ZONE:
                raise SimulationError(
                    f"{label} is in flight and cannot take orders"
                )
            steps.append(self._check_order(drone, order))
        return steps

    def _check_order(self, drone: Drone, order: MoveOrder) -> _Step:
        """Check one order's target zone and the connection to it.

        Args:
            drone: The drone the order is for, standing in a zone.
            order: The order to check.

        Returns:
            The departure step for the order.

        Raises:
            SimulationError: If the zone is unknown, blocked, the one the
                drone is in, or not connected to it.
        """
        label = f"D{drone.drone_id}"
        try:
            zone = self.network.get_zone(order.zone_name)
        except ZoneNotFoundError:
            raise SimulationError(
                f"{label} ordered into unknown zone {order.zone_name!r}"
            ) from None
        if not zone.zone_type.is_traversable:
            raise SimulationError(
                f"{label} ordered into blocked zone {zone.name!r}"
            )
        here = drone.current_zone
        if here == zone.name:
            raise SimulationError(
                f"{label} ordered to move into {here!r}, where it already "
                "is; to wait, give it no order"
            )
        connection = (
            None if here is None
            else self.network.connection_between(here, zone.name)
        )
        if connection is None:
            raise SimulationError(
                f"{label} ordered from {here!r} to {zone.name!r}, "
                "which are not connected"
            )
        return _Step(drone, connection, zone, is_arrival=False)

    def _check_links(
        self, state: SimulationState, steps: list[_Step]
    ) -> None:
        """Check that no connection has too many departures this turn.

        Args:
            state: The state before the turn.
            steps: The turn's checked steps.

        Raises:
            SimulationError: If a connection is used by more drones than
                its ``max_link_capacity``.
        """
        # Landing drones leave their connection this turn, so only the
        # departures use connection capacity.
        usage: dict[str, int] = {}
        for step in steps:
            if step.is_arrival:
                continue
            name = step.connection.name
            usage[name] = usage.get(name, 0) + 1
            if usage[name] > step.connection.max_link_capacity:
                raise SimulationError(
                    f"turn {state.turn_number + 1}: connection {name!r} "
                    f"used by more than {step.connection.max_link_capacity} "
                    "drone(s)"
                )

    def _check_zones(
        self, state: SimulationState, steps: list[_Step]
    ) -> None:
        """Check every zone's drone count at the end of the turn.

        Args:
            state: The state before the turn.
            steps: The turn's checked steps.

        Raises:
            SimulationError: If a zone would hold more drones than its
                capacity, naming the stuck drone if one cannot land.
        """
        delta, landing = self._zone_changes(steps)
        for name, change in delta.items():
            limit = self.network.get_zone(name).capacity
            if change <= 0 or limit is None:
                continue
            if state.occupancy(name) + change <= limit:
                continue
            turn = state.turn_number + 1
            stuck = landing.get(name)
            if stuck is not None:
                raise SimulationError(
                    f"turn {turn}: D{stuck.drone.drone_id} is stuck on "
                    f"connection {stuck.connection.name!r}: zone {name!r} "
                    "is full"
                )
            raise SimulationError(
                f"turn {turn}: zone {name!r} would hold more than "
                f"{limit} drone(s)"
            )

    @staticmethod
    def _zone_changes(
        steps: list[_Step],
    ) -> tuple[dict[str, int], dict[str, _Step]]:
        """Count how the turn changes each zone's drone count.

        Args:
            steps: The turn's checked steps.

        Returns:
            The change of each zone's drone count, and the first drone
            landing in each zone from a connection.
        """
        delta: dict[str, int] = {}
        landing: dict[str, _Step] = {}
        for step in steps:
            name = step.zone.name
            if step.is_arrival:
                landing.setdefault(name, step)  # lowest drone_id first
            else:
                source = step.drone.current_zone
                if source is not None:
                    delta[source] = delta.get(source, 0) - 1
                if step.zone.zone_type is ZoneType.RESTRICTED:
                    continue  # on the connection until next turn
            delta[name] = delta.get(name, 0) + 1
        return delta, landing

    @staticmethod
    def _apply(state: SimulationState, step: _Step) -> Move:
        """Apply one checked step to the state.

        Args:
            state: The state to change.
            step: The step to apply.

        Returns:
            The move as it appears in the output.
        """
        drone_id = step.drone.drone_id
        if step.is_arrival:
            state.complete_transit(drone_id)
            return Move(drone_id, step.zone.name)
        link = step.connection.name
        if step.zone.zone_type is ZoneType.RESTRICTED:
            state.enter_transit(drone_id, step.connection, step.zone.name)
            return Move(drone_id, destination=link, connection_name=link)
        state.enter_zone(drone_id, step.zone.name)
        return Move(drone_id, destination=step.zone.name, connection_name=link)


# --- TurnObserver -----------------------------------------------------

class TurnObserver(Protocol):
    """Anything that follows the simulation as it runs.

    ``SimulationEngine.run`` calls ``begin`` once before the first turn,
    ``render`` after every applied turn, and ``close`` once at the end,
    even when the run stops with an error. Observers only read the state.
    The turn log printer and every view are observers.
    """

    def begin(self, state: SimulationState) -> None:
        """Take the initial state (turn 0, every drone in the start zone).

        Args:
            state: The state before the first turn.
        """
        ...

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Take the state after a turn.

        Args:
            state: The state with the turn applied.
            moves: The moves made during that turn, in drone_id order.
        """
        ...

    def close(self) -> None:
        """Release whatever the observer holds (e.g. a window)."""
        ...


class ObserverGroup:
    """Forwards every call to each of its observers, in order.

    The application uses it to give the engine the turn log printer and
    the chosen views as a single observer.
    """

    def __init__(self, observers: Sequence[TurnObserver]) -> None:
        """Keep the observers to forward to.

        Args:
            observers: The observers, in the order they are called.
        """
        self.observers: list[TurnObserver] = list(observers)

    def begin(self, state: SimulationState) -> None:
        """Give the initial state to every observer.

        Args:
            state: The state before the first turn.
        """
        for observer in self.observers:
            observer.begin(state)

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Give the turn to every observer.

        Args:
            state: The state with the turn applied.
            moves: The moves made during that turn, in drone_id order.
        """
        for observer in self.observers:
            observer.render(state, moves)

    def close(self) -> None:
        """Close every observer, even if closing one of them fails.

        Observers are closed in order. If several fail, the last failure is
        raised, with the earlier ones chained to it as context.
        """
        self._close_from(0)

    def _close_from(self, index: int) -> None:
        """Close observers[index:]; ``finally`` chains failures as context.

        Args:
            index: The first observer to close.
        """
        if index >= len(self.observers):
            return
        try:
            self.observers[index].close()
        finally:
            self._close_from(index + 1)


# --- SimulationEngine -------------------------------------------------

class MoveDecider(Protocol):
    """Anything that decides each turn's moves (the ``Scheduler``)."""

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Return the orders for the turn after ``state``.

        Args:
            state: The current state.

        Returns:
            The orders for drones standing in zones.
        """
        ...


def default_turn_limit(world: World) -> int:
    """Return a turn count no sensible schedule should ever exceed.

    It is a safety limit to catch a scheduler that loops forever, not a
    bound proved for every schedule: sending the drones one at a time is
    always possible and needs about two turns per zone per drone, so
    ``2 * zones * nb_drones`` turns is far more than any real run takes.

    Args:
        world: The parsed map and drone count.

    Returns:
        ``2 * zones * nb_drones`` (at least one zone is counted).
    """
    return 2 * max(len(world.network.zones), 1) * world.nb_drones


class SimulationEngine:
    """Drives the turn-by-turn simulation from start to full delivery.

    Composes the state, the rules (``TurnResolver``) and the decisions
    (any ``MoveDecider``, normally the ``Scheduler``): each turn the
    decider orders moves, the resolver checks and applies them, and the
    resulting moves are recorded.
    """

    def __init__(
        self,
        world: World,
        decider: MoveDecider,
        max_turns: int | None = None,
    ) -> None:
        """Set up all drones in the start zone.

        Args:
            world: The parsed map and drone count.
            decider: Decides each turn's moves (normally a ``Scheduler``).
            max_turns: Safety limit on the number of turns; defaults to
                ``default_turn_limit(world)``.
        """
        self.world = world
        self.decider = decider
        self.state = SimulationState(world.network, world.nb_drones)
        self.resolver = TurnResolver(world.network)
        self.max_turns = (
            default_turn_limit(world) if max_turns is None else max_turns
        )

    def run(
        self, observer: TurnObserver | None = None
    ) -> list[list[Move]]:
        """Run the simulation to completion.

        Args:
            observer: Optional observer: ``begin`` is called before the
                first turn, ``render(state, moves)`` after every applied
                turn, and ``close`` once at the end, even on error
                (including an error raised by ``begin``).

        Returns:
            All turns, each a list of the moves made during that turn, in
            drone_id order. No turn is empty.

        Raises:
            SimulationError: If the scheduler orders an illegal move, if a
                drone in flight cannot land (stuck on its connection), if a
                turn passes with no drone moving (the state would never
                change again), or if ``max_turns`` is exceeded.
        """
        turns: list[list[Move]] = []
        try:
            if observer is not None:
                observer.begin(self.state)
            while not self.state.is_complete:
                turns.append(self._play_turn())
                if observer is not None:
                    observer.render(self.state, turns[-1])
        finally:
            if observer is not None:
                observer.close()
        return turns

    def _play_turn(self) -> list[Move]:
        """Order, check and apply one turn; return its moves.

        Returns:
            The turn's moves, in drone_id order (never empty).

        Raises:
            SimulationError: On an illegal order, a turn where nothing
                moves, or when ``max_turns`` is reached.
        """
        if self.state.turn_number >= self.max_turns:
            raise SimulationError(
                f"not finished after {self.max_turns} turns "
                f"({self.state.delivered_count}/{self.world.nb_drones} "
                "drones delivered)"
            )
        orders = self.decider.decide_moves(self.state)
        moves = self.resolver.resolve(self.state, orders)
        if not moves:
            raise SimulationError(
                f"turn {self.state.turn_number}: no drone moved, "
                "so the simulation cannot progress"
            )
        return moves
