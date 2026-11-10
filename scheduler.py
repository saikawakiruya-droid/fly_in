"""The Scheduler: each turn, pulls the drones along the flow map.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* Departure: the route a drone takes, and the turn it leaves on.
* plan_departures: gives every drone a route and a turn to leave on.
* Scheduler: decides, each turn, which drone moves where.
"""

from dataclasses import dataclass

from engine import Drone, DroneStatus, MoveOrder, SimulationState
from errors import SimulationError
from pathfinder import FlowMap, Pathfinder, Route
from world import Network


# --- Departure --------------------------------------------------------

@dataclass(frozen=True)
class Departure:
    """When a drone leaves the start zone, and along which route.

    Attributes:
        route: The route the drone follows all the way to the end zone.
        turn: The turn it leaves the start zone on (1 for the first).
    """

    route: Route
    turn: int


def plan_departures(
    flow_map: FlowMap, nb_drones: int
) -> dict[int, Departure]:
    """Give every drone a route and a turn to leave the start zone on.

    Each route has ``rate`` seats per turn, from turn 1 on, for as long as
    a drone taking one arrives by ``flow_map.last_turn``. The drones take
    the seats that arrive first (then the ones that leave first, then the
    first route), in drone_id order. A longer route is therefore taken
    only when waiting for a seat on a shorter one would arrive later.

    Args:
        flow_map: The held map and its routes.
        nb_drones: The drones to send, numbered from 1.

    Returns:
        The departure of every drone, by drone_id.

    Raises:
        SimulationError: If the routes have fewer seats than drones (the
            flow map is wrong).
    """
    seats: list[tuple[int, int, int]] = []
    for index, route in enumerate(flow_map.routes):
        for turn in range(1, flow_map.last_turn - route.turns + 2):
            seats.extend(
                [(route.arrival_turn(turn), turn, index)] * route.rate
            )
    if len(seats) < nb_drones:
        raise SimulationError(
            f"the flow map has {len(seats)} seats for {nb_drones} drones"
        )
    seats.sort()
    return {
        drone_id: Departure(flow_map.routes[index], turn)
        for drone_id, (_, turn, index) in enumerate(
            seats[:nb_drones], start=1
        )
    }


# --- Scheduler --------------------------------------------------------

class Scheduler:
    """Moves the drones along the routes of the flow map.

    Before the first turn, the ``Pathfinder`` builds the flow map (the
    held map and its routes), and every drone gets a route and a turn to
    leave on (``plan_departures``). Each turn, the zones of the held map
    are visited nearest to the end zone first, and each zone pulls in the
    drones whose next zone on their route it is: drones in the start zone
    whose turn to leave has come, and every drone already on its way (they
    never wait).

    Each pull is checked against the held map: the drone has never been
    in the zone (its ``history``), the connection still has room this
    turn, and the zone still has a seat among the drones entering it this
    turn. The held map's capacities are what the routes send per turn,
    so the checks always pass; if one fails, the flow map is wrong and a
    ``SimulationError`` is raised instead of breaking a rule.

    Every run ends: each drone makes as many moves as its route has steps.

    ``decide_moves`` only reads the state, so calling it again for the
    same turn gives the same orders. A state at turn 0 (a new simulation)
    builds the flow map again.
    """

    def __init__(self, network: Network, pathfinder: Pathfinder) -> None:
        """Keep the map; the flow map is built on the first turn.

        Args:
            network: The map being simulated.
            pathfinder: Builds the flow map.
        """
        self.network = network
        self.pathfinder = pathfinder
        self._flow_map: FlowMap | None = None
        self._departures: dict[int, Departure] = {}
        self._pull_order: list[str] = []

    @property
    def flow_map(self) -> FlowMap | None:
        """Return the flow map in use, or None before the first turn."""
        return self._flow_map

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Decide this turn's moves for the drones standing in zones.

        Args:
            state: The state after the turns played so far.

        Returns:
            At most one order per drone, in pull order; drones without an
            order wait (only in the start zone) or are in flight.

        Raises:
            SimulationError: If the state does not follow the flow map
                (a drone off its route, or a check that fails).
        """
        flow_map = self._flow_map
        if flow_map is None or state.turn_number == 0:
            flow_map = self._plan(len(state.drones))
        turn = state.turn_number + 1
        pulled = self._drones_to_pull(state, turn)
        entering: dict[str, int] = {}
        along: dict[str, int] = {}
        orders: list[MoveOrder] = []
        for zone_name in self._pull_order:
            for drone in pulled.get(zone_name, []):
                self._check(flow_map.network, drone, zone_name, entering,
                            along)
                orders.append(MoveOrder(drone.drone_id, zone_name))
        return orders

    def _plan(self, nb_drones: int) -> FlowMap:
        """Build the flow map, the departures and the pull order.

        Args:
            nb_drones: The drones to send.

        Returns:
            The flow map.
        """
        flow_map = self.pathfinder.flow_map(nb_drones)
        self._flow_map = flow_map
        self._departures = plan_departures(flow_map, nb_drones)
        self._pull_order = self._zones_nearest_first(flow_map)
        return flow_map

    def _zones_nearest_first(self, flow_map: FlowMap) -> list[str]:
        """Return the zones a drone can be pulled into, in pull order.

        Args:
            flow_map: The held map and its routes.

        Returns:
            Every zone of the routes but the start zone, by the turns left
            to the end zone from them along their routes (fewest first),
            then in declaration order.
        """
        turns_left: dict[str, int] = {}
        for route in flow_map.routes:
            turns = 0
            for name in reversed(route.zones[1:]):
                turns_left[name] = min(turns_left.get(name, turns), turns)
                turns += self.network.get_zone(name).zone_type.turn_cost
        declared = {
            name: index for index, name in enumerate(self.network.zones)
        }
        return sorted(
            turns_left, key=lambda name: (turns_left[name], declared[name])
        )

    def _drones_to_pull(
        self, state: SimulationState, turn: int
    ) -> dict[str, list[Drone]]:
        """Return the drones that move this turn, by the zone they enter.

        Args:
            state: The state before the turn.
            turn: The turn being decided.

        Returns:
            For each zone, the drones to pull into it, in drone_id order.

        Raises:
            SimulationError: If a drone is off its route, or still in the
                start zone after its turn to leave.
        """
        start = self.network.start_zone.name
        pulled: dict[str, list[Drone]] = {}
        for drone in state.active_drones():
            here = drone.current_zone
            if drone.status is not DroneStatus.AT_ZONE or here is None:
                continue
            departure = self._departures.get(drone.drone_id)
            if departure is None:
                raise SimulationError(f"D{drone.drone_id} has no route")
            if here == start and departure.turn != turn:
                if departure.turn < turn:
                    raise SimulationError(
                        f"D{drone.drone_id} missed its turn {departure.turn} "
                        "to leave"
                    )
                continue
            zones = departure.route.zones
            next_step = len(drone.history)
            on_route = zones[:next_step] == tuple(drone.history)
            if not on_route or next_step >= len(zones):
                raise SimulationError(
                    f"D{drone.drone_id} is in {here!r}, off its route"
                )
            pulled.setdefault(zones[next_step], []).append(drone)
        return pulled

    @staticmethod
    def _check(
        held: Network,
        drone: Drone,
        target: str,
        entering: dict[str, int],
        along: dict[str, int],
    ) -> None:
        """Check one pull against the held map, and count it.

        Args:
            held: The held map.
            drone: The drone pulled, standing in a zone.
            target: The zone pulling it.
            entering: Drones pulled into each zone so far this turn.
            along: Drones sent along each connection so far this turn.

        Raises:
            SimulationError: If the drone has been in the zone, or the
                connection or the zone of the held map is full.
        """
        label = f"D{drone.drone_id}"
        here = drone.current_zone
        if target in drone.history:
            raise SimulationError(f"{label} would go back into {target!r}")
        connection = (
            None if here is None else held.connection_between(here, target)
        )
        if connection is None:
            raise SimulationError(
                f"the flow map has no connection {here!r}-{target!r}"
            )
        along[connection.name] = along.get(connection.name, 0) + 1
        if along[connection.name] > connection.max_link_capacity:
            raise SimulationError(
                f"{label}: connection {connection.name!r} of the flow map "
                "is full"
            )
        entering[target] = entering.get(target, 0) + 1
        capacity = held.get_zone(target).capacity
        if capacity is not None and entering[target] > capacity:
            raise SimulationError(
                f"{label}: zone {target!r} of the flow map is full"
            )
