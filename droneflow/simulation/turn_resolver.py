"""TurnResolver: checks a turn of orders against the rules, then applies it."""

from dataclasses import dataclass

from ..errors import SimulationError, ZoneNotFoundError
from ..models.connection import Connection
from ..models.drone import Drone, DroneStatus
from ..models.network import Network
from ..models.zone import Zone, ZoneType
from .state import Move, MoveOrder, SimulationState


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
        """Check moves against ``network``."""
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
        label = f"D{drone.drone_id}"
        try:
            zone = self.network.get_zone(order.zone)
        except ZoneNotFoundError:
            raise SimulationError(
                f"{label} ordered into unknown zone {order.zone!r}"
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
    def _apply(state: SimulationState, step: _Step) -> Move:
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
