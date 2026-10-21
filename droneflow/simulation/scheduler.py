"""Scheduler: decides, each turn, which drone moves where."""

from ..errors import SimulationError
from ..models.drone import Drone, DroneStatus
from ..models.network import Network
from ..pathfinding.pathfinder import Hop, Pathfinder
from .detour_policy import DetourPolicy
from .evictor import Evictor
from .hop_taker import HopTaker
from .positions import PositionBoard
from .reservation_table import ReservationTable
from .state import MoveOrder, SimulationState
from .turn_ledger import TurnLedger
from .zone_ranking import ZoneRanking


class Scheduler:
    """Moves every drone one step toward the end zone whenever it can.

    The scheduler keeps a ``ReservationTable`` of planned moves from turn
    to turn: drones landing in restricted zones, and evictions (a drone
    standing in a zone, scheduled to move on at a given turn to make room
    for a drone that will enter that zone). Each turn:

    1. drones in flight toward a restricted zone get no order (the
       ``TurnResolver`` lands them; their landings are in the table);
    2. the planned moves due this turn are ordered first;
    3. the other drones standing in zones are decided zone by zone, in
       the order of the ``ZoneRanking`` (closest to the end zone first;
       then priority route, fewer exits, declaration order). Drones in the
       same zone have the same shortest hops (their detours may differ, as
       each drone has been in different zones) and keep ``active_drones``
       order. A drone that has a planned eviction, from an earlier turn or
       from an earlier decision this turn, is decided like the others: its
       planned move is dropped if it can move now, and kept otherwise.

    A drone takes the first hop of ``Pathfinder.next_hops`` (shortest moves
    only, priority zones first) that has room according to a ``TurnLedger``:
    the connection has room this turn, and the zone entered has a seat on
    the turn the drone enters it and on every later turn with a planned move.
    If no hop has room, the hops are tried again in the same order, this
    time letting an ``Evictor`` make room (eviction is a last resort;
    the ``HopTaker`` does both rounds):

    * into a restricted zone: occupants of the zone are evicted so that it
      has a seat from the landing turn on;
    * into another zone that has a seat this turn but not on a later turn
      (the seat is kept for a drone planned to enter): the drone enters, and
      the zone's occupants, the drone itself included, are evicted so that
      the zone is never over capacity on those turns.

    If that fails too, the drone tries the detours its ``DetourPolicy``
    allows (moves off the shortest routes, never into a zone the drone has
    been in, when they are expected to be no slower than queuing behind the
    drones ahead), the same two ways: without evicting, then letting the
    ``Evictor`` make room. Otherwise it waits.

    Every run ends. A shortest move (planned evictions included) strictly
    lowers the drone's distance to the end zone, and a detour enters a zone
    the drone has never been in, so each drone makes finitely many moves.
    And at least one drone moves each turn: planned moves and landings
    always happen, and otherwise the drone closest to the goal always has
    free room on its shortest route, which it tries first.

    ``decide_moves`` is meant to be called once per turn, in turn order.
    Called again for the same turn, it drops the moves it planned for that
    turn and plans it again from the state it is given (landings
    included); called for an earlier turn (a new simulation), it starts
    over with an empty table.
    """

    def __init__(self, network: Network, pathfinder: Pathfinder) -> None:
        """Keep the network and cache what never changes during a run.

        Args:
            network: The map being simulated.
            pathfinder: Answers distances, shortest hops and detours.
        """
        self.network = network
        self.pathfinder = pathfinder
        self._hops: dict[str, list[Hop]] = {
            name: pathfinder.next_hops(name) for name in network.zones
        }
        self._detour_policy = DetourPolicy(pathfinder, self._hops)
        self._ranking = ZoneRanking(
            network, pathfinder, self._hops, self._detour_policy
        )
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
                zone cannot be reached.
        """
        self._start_turn(state)
        ledger = TurnLedger(state, self._table)
        board = PositionBoard.from_state(state)
        self._detour_policy.remember(ledger.turn, board)
        orders: list[MoveOrder] = []
        for move in self._table.due(ledger.turn):
            orders.append(MoveOrder(move.drone_id, move.zone))
            board.place(move.drone_id, move.zone, move.arrive_turn)
        ordered = {order.drone_id for order in orders}
        taker = HopTaker(
            ledger,
            Evictor(ledger, self._table, self._hops, board),
            board,
        )
        for drone in self._decision_order(state, ordered):
            order = self._decide(drone, ledger.turn, taker, board)
            if order is not None:
                orders.append(order)
        return orders

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

    def _decide(
        self,
        drone: Drone,
        turn: int,
        taker: HopTaker,
        board: PositionBoard,
    ) -> MoveOrder | None:
        """Pick the drone's move this turn, or None if it waits.

        A drone holding a planned eviction (from an earlier turn, or from
        an earlier decision this turn) first gives it up; it gets it back
        if it cannot move now.
        """
        drone_id = drone.drone_id
        here = self._zone_of(drone)
        mark = self._table.mark()
        if self._table.leaves_after(drone_id, turn):
            self._table.remove(drone_id)
        hop = taker.take_first(drone_id, here, self._hops.get(here, []))
        if hop is None:
            detours = self._detour_policy.allowed(drone_id, here, board)
            hop = taker.take_first(drone_id, here, detours)
        if hop is not None:
            return MoveOrder(drone_id, hop.zone.name)
        self._table.rollback(mark)
        return None

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

    def _decision_key(self, drone: Drone) -> int:
        here = self._zone_of(drone)
        rank = self._ranking.rank(here)
        if rank is None:
            raise SimulationError(
                f"D{drone.drone_id} is in {here!r}, which cannot reach "
                "the end zone"
            )
        return rank

    @staticmethod
    def _zone_of(drone: Drone) -> str:
        if drone.current_zone is None:
            raise SimulationError(f"D{drone.drone_id} is not in a zone")
        return drone.current_zone
