"""Scheduler: decides, each turn, which drone moves where."""

from ..errors import SimulationError
from ..models.drone import Drone, DroneStatus
from ..models.network import Network
from ..models.zone import ZoneType
from ..pathfinding.pathfinder import Hop, Pathfinder
from .detour_policy import DetourPolicy
from .evictor import Evictor, Position
from .reservation_table import ReservationTable
from .state import MoveOrder, SimulationState
from .turn_ledger import TurnLedger


class Scheduler:
    """Moves every drone one shortest step forward whenever there is room.

    The scheduler keeps a ``ReservationTable`` of planned moves from turn
    to turn: drones landing in restricted zones, and evictions (a drone
    standing in a zone, scheduled to move on at a given turn to make room
    for a drone that will enter that zone). Each turn:

    1. drones in flight toward a restricted zone get no order (the engine
       lands them; their landings are in the table);
    2. the planned moves due this turn are ordered first;
    3. the other drones standing in zones are decided closest to the end
       zone first, so drones leaving a zone free its room before the drones
       behind them ask for it; among drones at the same distance, those on
       the priority route (see ``is_on_priority_route``) come first, then by
       drone_id. A drone evicted earlier in this turn's decisions waits:
       its move is planned for a later turn.

    A drone takes the first hop of ``Pathfinder.next_hops`` (shortest moves
    only, priority zones first) that has room according to a ``TurnLedger``:
    the connection has room this turn, and the zone entered has a seat on
    the turn the drone enters it and on every later turn with a planned move.
    If no hop has room, the hops are tried again in the same order, this
    time letting an ``Evictor`` make room (eviction is a last resort):

    * into a restricted zone: occupants of the zone are evicted so that it
      has a seat from the landing turn on;
    * into another zone that has a seat this turn but not on a later turn
      (the seat is kept for a drone planned to enter): the drone enters, and
      the zone's occupants, the drone itself included, are evicted so that
      the zone is never over capacity on those turns.

    If that fails too, the drone tries the detours its ``DetourPolicy``
    allows (longer routes that still lower its distance, when they cost no
    more than waiting behind the drones ahead), the same two ways: without
    evicting, then letting the ``Evictor`` make room. Otherwise it waits.

    A drone with a planned eviction may still move earlier by an ordinary
    decision; its planned move is then dropped (it has left already).

    Every move, detours included, strictly lowers the drone's distance to
    the end zone, so drones never wait on each other in a cycle: planned
    moves and landings always happen, and otherwise the drone closest to
    the goal always has free room ahead, so at least one drone moves each
    turn.

    ``decide_moves`` is meant to be called once per turn, in turn order.
    Called again for the same turn, it drops the moves it planned for that
    turn and plans it again from the state it is given (landings
    included); called for an earlier turn (a new simulation), it starts
    over with an empty table.
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
        self._detours = DetourPolicy(pathfinder, self._hops)
        self._table = ReservationTable()
        self._planned_turn: int | None = None
        self._turn_mark = 0

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Decide this turn's moves for the drones standing in zones.

        Returns:
            At most one order per drone: first the planned moves due this
            turn, then the decided ones in decision order; drones without
            an order wait. Every order is legal under ``TurnResolver``.

        Raises:
            SimulationError: If a drone stands in a zone from which the end
                zone cannot be reached (it can never get there by following
                shortest hops).
        """
        self._start_turn(state)
        ledger = TurnLedger(state, self._table)
        positions = self._positions(state)
        orders: list[MoveOrder] = []
        for move in self._table.due(ledger.turn):
            orders.append(MoveOrder(move.drone_id, move.zone))
            positions[move.drone_id] = (move.zone, move.arrive_turn)
        ordered = {order.drone_id for order in orders}
        holding = {
            drone_id for drone_id in positions
            if self._leaves_later(drone_id, ledger.turn)
        }
        evictor = Evictor(ledger, self._hops, positions)
        for drone in self._decision_order(state, ordered):
            drone_id = drone.drone_id
            if drone_id not in holding and self._leaves_later(
                drone_id, ledger.turn
            ):
                continue  # evicted during this turn's decisions
            order = self._decide(
                drone, ledger, evictor, positions, drone_id in holding
            )
            if order is not None:
                orders.append(order)
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

    def _start_turn(self, state: SimulationState) -> None:
        """Prepare the table for the state's next turn.

        Called again for the same turn, the moves planned for that turn are
        undone first, then the table is prepared from the given state like
        on the first call (its landings replace the previous ones).
        """
        turn = state.turn_number + 1
        if self._planned_turn == turn:
            self._table.rollback(self._turn_mark)
        elif self._planned_turn is not None and turn < self._planned_turn:
            self._table.clear()
        self._table.start_turn(state)
        self._turn_mark = self._table.mark()
        self._planned_turn = turn

    def _positions(self, state: SimulationState) -> dict[int, Position]:
        """Return where each drone on the map is, and since when, for sure.

        Drones standing in a zone have been there since the end of the
        turn just played; drones in flight are there from this turn on.
        """
        played = state.turn_number
        positions: dict[int, Position] = {}
        for drone in state.active_drones():
            if drone.status is DroneStatus.IN_TRANSIT:
                if drone.transit_target is not None:
                    positions[drone.drone_id] = (
                        drone.transit_target, played + 1
                    )
            elif drone.current_zone is not None:
                positions[drone.drone_id] = (drone.current_zone, played)
        return positions

    def _leaves_later(self, drone_id: int, turn: int) -> bool:
        return any(
            move.depart_turn > turn for move in self._table.planned(drone_id)
        )

    def _decide(
        self,
        drone: Drone,
        ledger: TurnLedger,
        evictor: Evictor,
        positions: dict[int, Position],
        holding: bool,
    ) -> MoveOrder | None:
        """Pick the drone's move this turn, or None if it waits.

        A drone holding a planned eviction first gives it up; it gets it
        back if it cannot move now.
        """
        here = self._zone_of(drone)
        mark = self._table.mark()
        if holding:
            self._table.remove(drone.drone_id)
        hop = self._first_hop(
            drone.drone_id, here, self._hops.get(here, []),
            ledger, evictor, positions,
        )
        if hop is None:
            hop = self._first_hop(
                drone.drone_id, here, self._detours.allowed(here, positions),
                ledger, evictor, positions,
            )
        if hop is not None:
            return MoveOrder(drone.drone_id, hop.zone.name)
        self._table.rollback(mark)
        return None

    def _first_hop(
        self,
        drone_id: int,
        here: str,
        hops: list[Hop],
        ledger: TurnLedger,
        evictor: Evictor,
        positions: dict[int, Position],
    ) -> Hop | None:
        """Record and return the first hop with room, or None.

        The hops are tried in order without evicting anyone, then again
        letting the ``Evictor`` make room.
        """
        for may_evict in (False, True):
            for hop in hops:
                if self._try_hop(
                    drone_id, here, hop, may_evict,
                    ledger, evictor, positions,
                ):
                    return hop
        return None

    @staticmethod
    def _try_hop(
        drone_id: int,
        here: str,
        hop: Hop,
        may_evict: bool,
        ledger: TurnLedger,
        evictor: Evictor,
        positions: dict[int, Position],
    ) -> bool:
        """Record the move along ``hop`` if it can be made; return whether.

        Without ``may_evict`` the hop is taken only if it has room as it is.
        """
        if not ledger.link_free(hop.connection, ledger.turn):
            return False
        zone = hop.zone
        arrive = ledger.arrival_turn(zone)
        if ledger.has_seats(zone, arrive):
            ledger.record(here, hop)
            positions[drone_id] = (zone.name, arrive)
            return True
        if not may_evict:
            return False
        if zone.zone_type is ZoneType.RESTRICTED:
            if not evictor.make_room(zone, arrive, 1):
                return False
            ledger.record(here, hop)
            positions[drone_id] = (zone.name, arrive)
            return True
        # Room now, but a seat kept for later is taken: enter, then evict.
        if not ledger.has_seat(zone, arrive, 1):
            return False
        ledger.record(here, hop)
        positions[drone_id] = (zone.name, arrive)
        if evictor.make_room(zone, arrive + 1, 0):
            return True
        ledger.cancel(here, hop)
        positions[drone_id] = (here, ledger.turn - 1)
        return False

    def _decision_order(
        self, state: SimulationState, ordered: set[int]
    ) -> list[Drone]:
        drones = [
            drone for drone in state.active_drones()
            if drone.status is DroneStatus.AT_ZONE
            and drone.drone_id not in ordered
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

    @staticmethod
    def _zone_of(drone: Drone) -> str:
        if drone.current_zone is None:
            raise SimulationError(f"D{drone.drone_id} is not in a zone")
        return drone.current_zone
