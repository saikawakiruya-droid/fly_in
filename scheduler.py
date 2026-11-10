"""The Scheduler and the parts that decide each turn's moves.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* DetourPolicy: which longer moves a drone that would wait may take.
* ZoneRanking: the order in which the scheduler decides the zones.
* HopTaker: takes the first hop a drone can make this turn, and records it.
* Scheduler: decides, each turn, which drone moves where.
"""

from collections.abc import Mapping

from engine import Drone, DroneStatus, MoveOrder, SimulationState
from errors import SimulationError
from pathfinder import Hop, Pathfinder
from scheduler_reservation_table import (
    Evictor,
    PositionBoard,
    ReservationTable,
    TurnLedger,
)
from world import Network, ZoneType


# --- DetourPolicy -----------------------------------------------------

class DetourPolicy:
    """Lets a drone that cannot take a shortest hop go the long way round.

    A detour is one of ``Pathfinder.detour_hops`` from the drone's zone
    ``u`` into a zone ``v``. It may lead sideways or away from the end
    zone, but never into a zone the drone has already been in: that is
    what keeps drones from flowing back and forth. It is allowed when it
    is expected to be no slower than queuing on the shortest route:

        turn_cost(v) + distance(v) + queue(v) <= distance(u) + ahead(u)

    ``ahead(u)`` counts the drones in the zones that a shortest hop from
    ``u`` leads to, directly or further down: the drones the shortest
    route has to let through first. ``queue(v)`` counts the same for
    ``v``, plus the drones in ``v`` itself. Drones are counted where they
    will be after the moves decided so far this turn (landing targets for
    drones in flight).

    The policy remembers every zone each drone has been in, from the
    positions the scheduler reports at the start of each turn. It keeps
    them turn by turn, so planning a turn again (or an earlier turn, for a
    new simulation) first drops what was reported for that turn and later.
    """

    def __init__(
        self, pathfinder: Pathfinder, hops: Mapping[str, list[Hop]]
    ) -> None:
        """Cache every zone's detours and the zones below it.

        Args:
            pathfinder: Answers distances and detour hops.
            hops: The shortest next hops of every zone.
        """
        self.pathfinder = pathfinder
        self._costed_detours: dict[str, list[tuple[int, Hop]]] = {
            name: self._costed(pathfinder, name) for name in hops
        }
        self._below: dict[str, set[str]] = {
            name: self._zones_below(name, hops) for name in hops
        }
        self._queue_zones: dict[str, set[str]] = {
            name: below | {name} for name, below in self._below.items()
        }
        self._reported: dict[int, dict[int, str]] = {}
        self._visited: dict[int, set[str]] = {}

    def detours(self, zone_name: str) -> list[Hop]:
        """Return the zone's detour hops, cheapest first.

        Args:
            zone_name: Name of the zone.

        Returns:
            The detour hops out of the zone (empty if it has none).

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        self.pathfinder.distance(zone_name)  # unknown names raise
        return [hop for _, hop in self._costed_detours.get(zone_name, [])]

    def remember(self, turn: int, board: PositionBoard) -> None:
        """Record where every drone is (or is landing) when ``turn`` starts.

        What was recorded for ``turn`` or a later turn is dropped first, so
        only the positions given for the turns before it count as visited.

        Args:
            turn: The turn about to be planned.
            board: Where every drone is (or is landing) at its start.
        """
        self._forget_from(turn)
        zone_names = board.zone_name_by_drone()
        self._reported[turn] = zone_names
        self._visit(zone_names)

    def allowed(
        self,
        drone_id: int,
        zone_name: str,
        board: PositionBoard,
    ) -> list[Hop]:
        """Return the detours this drone may take now, cheapest first.

        Args:
            drone_id: The drone deciding.
            zone_name: Where the drone stands.
            board: Where every drone on the map will be after the moves
                decided so far this turn (the scheduler's board).

        Returns:
            The allowed detours; empty if the zone cannot reach the end
            zone.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        distance = self.pathfinder.distance(zone_name)
        if distance is None:
            return []
        visited = self._visited.get(drone_id, set())
        candidates = [
            (total, hop) for total, hop in self._costed_detours[zone_name]
            if hop.zone.name not in visited
        ]
        if not candidates:
            return []
        budget = distance + board.count_in(self._below[zone_name])
        return [
            hop for total, hop in candidates
            if total + board.count_in(self._queue_zones[hop.zone.name])
            <= budget
        ]

    def _forget_from(self, turn: int) -> None:
        """Drop the positions reported for ``turn`` and later turns.

        The visited zones are then rebuilt from the earlier reports.

        Args:
            turn: The first turn whose report to drop.
        """
        if any(earlier >= turn for earlier in self._reported):
            self._reported = {
                earlier: zone_names
                for earlier, zone_names in self._reported.items()
                if earlier < turn
            }
            self._visited = {}
            for zone_names in self._reported.values():
                self._visit(zone_names)

    def _visit(self, zone_names: Mapping[int, str]) -> None:
        """Mark each drone's zone as visited by that drone.

        Args:
            zone_names: The zone name by drone_id.
        """
        for drone_id, zone_name in zone_names.items():
            self._visited.setdefault(drone_id, set()).add(zone_name)

    @staticmethod
    def _costed(pathfinder: Pathfinder, name: str) -> list[tuple[int, Hop]]:
        """Return the zone's detours with their total cost to the end.

        Args:
            pathfinder: Answers detour hops and route costs.
            name: Name of the zone.

        Returns:
            ``(route_cost, hop)`` pairs, in ``detour_hops`` order.
        """
        return [
            (pathfinder.route_cost(hop), hop)
            for hop in pathfinder.detour_hops(name)
        ]

    @staticmethod
    def _zones_below(name: str, hops: Mapping[str, list[Hop]]) -> set[str]:
        """Return the zones reachable from ``name`` by shortest hops.

        Args:
            name: Name of the zone to start from.
            hops: The shortest next hops of every zone.

        Returns:
            The zones below ``name`` (not including it).
        """
        below: set[str] = set()
        stack = [name]
        while stack:
            for hop in hops.get(stack.pop(), []):
                if hop.zone.name not in below:
                    below.add(hop.zone.name)
                    stack.append(hop.zone.name)
        return below


# --- ZoneRanking ------------------------------------------------------

class ZoneRanking:
    """Numbers the zones that can reach the end zone in decision order.

    Closest to the end zone first, so drones leaving a zone free its room
    before the drones behind them ask for it. Among zones at the same
    distance: zones on the priority route first, then zones with fewer
    exits (shortest hops and detours), so a drone with a choice does not
    take the only way out of another; then declaration order. The ranks
    are computed once.
    """

    def __init__(
        self,
        network: Network,
        pathfinder: Pathfinder,
        hops: Mapping[str, list[Hop]],
        detour_policy: DetourPolicy,
    ) -> None:
        """Rank every zone that can reach the end zone.

        Args:
            network: The map being simulated.
            pathfinder: Answers distances.
            hops: The shortest next hops of every zone.
            detour_policy: Answers each zone's detour hops.
        """
        self.network = network
        self._hops = hops
        keyed: list[tuple[tuple[int, bool, int, int], str]] = []
        for index, name in enumerate(network.zones):
            distance = pathfinder.distance(name)
            if distance is None:
                continue
            exits = len(hops[name]) + len(detour_policy.detours(name))
            key = (distance, not self.is_on_priority_route(name), exits, index)
            keyed.append((key, name))
        keyed.sort()
        self._rank = {name: rank for rank, (_, name) in enumerate(keyed)}

    def rank(self, zone_name: str) -> int | None:
        """Return the zone's place in decision order.

        Args:
            zone_name: Name of the zone.

        Returns:
            0 for the zone decided first, and so on; None if the zone
            cannot reach the end zone.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        self.network.get_zone(zone_name)
        return self._rank.get(zone_name)

    def is_on_priority_route(self, zone_name: str) -> bool:
        """Return whether a drone in this zone is on the priority route.

        It is if the zone itself is a priority zone, or if its first
        shortest next hop is one (``next_hops`` lists priority zones first,
        so this means any shortest next hop is a priority zone). Priority
        zones two or more hops away are not considered.

        Args:
            zone_name: Name of the zone.

        Returns:
            True if the zone or its first shortest next hop is a priority
            zone.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        if self.network.get_zone(zone_name).zone_type is ZoneType.PRIORITY:
            return True
        hops = self._hops.get(zone_name, [])
        return bool(hops) and hops[0].zone.zone_type is ZoneType.PRIORITY


# --- HopTaker ---------------------------------------------------------

class HopTaker:
    """Tries a drone's hops in order for one turn and records the first.

    A hop can be taken when its connection has room this turn and the zone
    it enters has a seat from the turn the drone enters it on, according
    to the ``TurnLedger``. The hops are first tried as they are; only if
    none fits are they tried again letting the ``Evictor`` make room
    (eviction is a last resort). Taking a hop records it in the ledger and
    moves the drone on the ``PositionBoard``.
    """

    def __init__(
        self, ledger: TurnLedger, evictor: Evictor, board: PositionBoard
    ) -> None:
        """Work on this turn's ledger, evictor and board.

        Args:
            ledger: The room left this turn and later.
            evictor: Makes room by evicting occupants (last resort).
            board: Where every drone will be.
        """
        self.ledger = ledger
        self.evictor = evictor
        self.board = board

    def take_first(
        self, drone_id: int, from_zone: str, hops: list[Hop]
    ) -> Hop | None:
        """Take the first of ``hops`` the drone can make, or return None.

        Args:
            drone_id: The drone to move.
            from_zone: The zone it leaves.
            hops: The hops to try, in order.

        Returns:
            The hop taken, or None if none can be made, even by evicting.
        """
        for may_evict in (False, True):
            for hop in hops:
                if self._take(drone_id, from_zone, hop, may_evict):
                    return hop
        return None

    def _take(
        self, drone_id: int, from_zone: str, hop: Hop, may_evict: bool
    ) -> bool:
        """Take ``hop`` if it can be made; return whether it was taken.

        Args:
            drone_id: The drone to move.
            from_zone: The zone it leaves.
            hop: The hop to try.
            may_evict: Whether the ``Evictor`` may make room.

        Returns:
            True if the hop was taken and recorded.
        """
        turn = self.ledger.planning_turn
        if not self.ledger.link_free(hop.connection, turn):
            return False
        arrive_turn = self.ledger.arrival_turn(hop.zone)
        if self.ledger.has_seat_from(hop.zone, arrive_turn):
            self._record(drone_id, from_zone, hop, arrive_turn)
            return True
        if not may_evict:
            return False
        if hop.zone.zone_type is ZoneType.RESTRICTED:
            return self._land_after_evicting(
                drone_id, from_zone, hop, arrive_turn
            )
        return self._enter_then_evict(drone_id, from_zone, hop, arrive_turn)

    def _land_after_evicting(
        self, drone_id: int, from_zone: str, hop: Hop, arrive_turn: int
    ) -> bool:
        """Fly to a full restricted zone if occupants can leave in time.

        The drone must land on ``arrive_turn`` (it cannot wait on the
        connection), so the zone needs one more seat (``extra=1``) from
        that turn on.

        Args:
            drone_id: The drone to move.
            from_zone: The zone it leaves.
            hop: The hop into the restricted zone.
            arrive_turn: The turn it lands.

        Returns:
            True if room was made and the hop recorded.
        """
        if not self.evictor.make_room(hop.zone, arrive_turn, 1):
            return False
        self._record(drone_id, from_zone, hop, arrive_turn)
        return True

    def _enter_then_evict(
        self, drone_id: int, from_zone: str, hop: Hop, arrive_turn: int
    ) -> bool:
        """Enter a zone whose seat is kept for a later drone, then evict.

        The zone has room now but not on a later turn, because a drone is
        planned to enter it then. The drone enters first, so it is already
        counted; the zone then needs no extra seat (``extra=0``) from the
        next turn on, and its occupants (this drone included) are evicted
        until it fits. If that fails, the move is undone.

        Args:
            drone_id: The drone to move.
            from_zone: The zone it leaves.
            hop: The hop into the zone.
            arrive_turn: The turn it enters the zone.

        Returns:
            True if the hop was recorded and room made; False if undone.
        """
        if not self.ledger.fits(hop.zone, arrive_turn, 1):
            return False
        before = self.board.where(drone_id)
        self._record(drone_id, from_zone, hop, arrive_turn)
        if self.evictor.make_room(hop.zone, arrive_turn + 1, 0):
            return True
        self.ledger.cancel(from_zone, hop)
        self.board.place(drone_id, before.zone_name, before.since_turn)
        return False

    def _record(
        self, drone_id: int, from_zone: str, hop: Hop, arrive_turn: int
    ) -> None:
        """Record the hop in the ledger and move the drone on the board.

        Args:
            drone_id: The drone to move.
            from_zone: The zone it leaves.
            hop: The hop it takes.
            arrive_turn: The turn it enters the hop's zone.
        """
        self.ledger.record(from_zone, hop)
        self.board.place(drone_id, hop.zone.name, arrive_turn)


# --- Scheduler --------------------------------------------------------

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
        """Cache what never changes during a run.

        Args:
            network: The map being simulated.
            pathfinder: Answers distances, shortest hops and detours.
        """
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

        Args:
            state: The state after the turns played so far.

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
        self._detour_policy.remember(ledger.planning_turn, board)
        orders = self._order_due_moves(ledger.planning_turn, board)
        ordered = {order.drone_id for order in orders}
        taker = HopTaker(
            ledger,
            Evictor(ledger, self._table, self._hops, board),
            board,
        )
        for drone in self._decision_order(state, ordered):
            order = self._decide(drone, ledger.planning_turn, taker, board)
            if order is not None:
                orders.append(order)
        return orders

    def _start_turn(self, state: SimulationState) -> None:
        """Prepare the table for the state's next turn.

        Called again for the same turn, the moves planned for that turn are
        undone first, then the table is prepared from the given state like
        on the first call (its landings replace the previous ones).

        Args:
            state: The state whose next turn is planned.
        """
        turn = state.turn_number + 1
        if self._planned_turn == turn:
            self._table.rollback(self._turn_mark)
        elif self._planned_turn is not None and turn < self._planned_turn:
            self._table.clear()
        self._table.start_turn(state)
        self._turn_mark = self._table.mark()
        self._planned_turn = turn

    def _order_due_moves(
        self, turn: int, board: PositionBoard
    ) -> list[MoveOrder]:
        """Order the moves planned for the turn, and place them on the board.

        Args:
            turn: The turn being planned.
            board: Where every drone will be; each move's drone is placed
                at its target.

        Returns:
            One order per move the table has due this turn.
        """
        orders: list[MoveOrder] = []
        for reservation in self._table.due(turn):
            orders.append(MoveOrder(reservation.drone_id, reservation.to_zone))
            board.place(
                reservation.drone_id,
                reservation.to_zone,
                reservation.arrive_turn,
            )
        return orders

    def _decision_order(
        self, state: SimulationState, ordered: set[int]
    ) -> list[Drone]:
        """Return the drones still to decide, in decision order.

        Args:
            state: The state at the start of the turn.
            ordered: The drones already given a planned move this turn.

        Returns:
            The drones standing in zones without an order, sorted by the
            ``ZoneRanking`` of their zone.
        """
        drones = [
            drone for drone in state.active_drones()
            if drone.status is DroneStatus.AT_ZONE
            and drone.drone_id not in ordered
        ]
        drones.sort(key=self._decision_key)
        return drones

    def _decision_key(self, drone: Drone) -> int:
        """Return the rank of the drone's zone, for sorting.

        Args:
            drone: A drone standing in a zone.

        Returns:
            The zone's rank in the ``ZoneRanking``.

        Raises:
            SimulationError: If the end zone cannot be reached from it.
        """
        here = self._zone_of(drone)
        rank = self._ranking.rank(here)
        if rank is None:
            raise SimulationError(
                f"D{drone.drone_id} is in {here!r}, which cannot reach "
                "the end zone"
            )
        return rank

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

        Args:
            drone: The drone to decide, standing in a zone.
            turn: The turn being planned.
            taker: Takes and records the first hop that fits.
            board: Where every drone will be.

        Returns:
            The drone's order, or None if it waits.
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

    @staticmethod
    def _zone_of(drone: Drone) -> str:
        """Return the zone the drone stands in.

        Args:
            drone: The drone to look at.

        Returns:
            Its zone's name.

        Raises:
            SimulationError: If the drone is not in a zone.
        """
        if drone.current_zone is None:
            raise SimulationError(f"D{drone.drone_id} is not in a zone")
        return drone.current_zone
