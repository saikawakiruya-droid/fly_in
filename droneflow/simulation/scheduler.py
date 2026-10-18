"""Scheduler: decides, each turn, which drone moves where."""

from ..errors import SimulationError
from ..models.drone import Drone, DroneStatus
from ..models.network import Network
from ..models.zone import ZoneType
from ..pathfinding.pathfinder import Hop, Pathfinder
from .state import MoveOrder, SimulationState
from .turn_ledger import TurnLedger


class Scheduler:
    """Moves every drone one shortest step forward whenever there is room.

    Each turn the drones standing in zones are considered one by one:

    1. drones in flight toward a restricted zone get no order (the engine
       lands them; their reservations are already counted in the state,
       and their connections are free again for this turn's orders);
    2. the others are decided closest to the end zone first, so drones
       leaving a zone free its room before the drones behind them ask for
       it;
    3. among drones at the same distance, those on the priority route
       (see ``is_on_priority_route``) come first, then by drone_id.

    A drone takes the first hop of ``Pathfinder.next_hops`` (shortest moves
    only, priority zones first) that still has room this turn according to
    a ``TurnLedger``, or waits if none has. It never takes a longer detour.

    Every move strictly lowers the drone's distance to the end zone, so
    drones never wait on each other in a cycle: the drone closest to the
    goal always has free room ahead, and at least one drone moves each turn.
    """

    def __init__(self, network: Network, pathfinder: Pathfinder) -> None:
        """Keep the network and cache the shortest next hops of every zone.

        Args:
            network: The map being simulated.
            pathfinder: Answers distances and shortest next hops.
        """
        self.network = network
        self.pathfinder = pathfinder
        self._hops: dict[str, list[Hop]] = {
            name: pathfinder.next_hops(name) for name in network.zones
        }

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Decide this turn's moves for the drones standing in zones.

        Returns:
            At most one order per drone, in decision order; drones without
            an order wait. Every order is legal under ``TurnResolver``.

        Raises:
            SimulationError: If a drone stands in a zone from which the end
                zone cannot be reached (it can never get there by following
                shortest hops).
        """
        ledger = TurnLedger(state)
        orders: list[MoveOrder] = []
        for drone in self._decision_order(state):
            here = self._zone_of(drone)
            hop = self._first_free_hop(here, ledger)
            if hop is None:
                continue
            ledger.record(here, hop)
            orders.append(MoveOrder(drone.drone_id, hop.zone.name))
        return orders

    def is_on_priority_route(self, zone_name: str) -> bool:
        """Return whether a drone in this zone is on the priority route.

        It is if the zone itself is a priority zone, or if its first
        shortest next hop is one (``next_hops`` lists priority zones first,
        so this means any shortest next hop is a priority zone). Priority
        zones two or more hops away are not considered.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        if self.network.get_zone(zone_name).zone_type is ZoneType.PRIORITY:
            return True
        hops = self._hops.get(zone_name, [])
        return bool(hops) and hops[0].zone.zone_type is ZoneType.PRIORITY

    def _decision_order(self, state: SimulationState) -> list[Drone]:
        drones = [
            drone for drone in state.active_drones()
            if drone.status is DroneStatus.AT_ZONE
        ]
        drones.sort(key=self._decision_key)
        return drones

    def _decision_key(self, drone: Drone) -> tuple[int, bool, int]:
        here = self._zone_of(drone)
        distance = self.pathfinder.distance(here)
        if distance is None:
            raise SimulationError(
                f"D{drone.drone_id} is in {here!r}, which cannot reach "
                "the end zone"
            )
        return (distance, not self.is_on_priority_route(here), drone.drone_id)

    def _first_free_hop(self, here: str, ledger: TurnLedger) -> Hop | None:
        for hop in self._hops.get(here, []):
            if ledger.has_room(hop):
                return hop
        return None

    @staticmethod
    def _zone_of(drone: Drone) -> str:
        if drone.current_zone is None:
            raise SimulationError(f"D{drone.drone_id} is not in a zone")
        return drone.current_zone
