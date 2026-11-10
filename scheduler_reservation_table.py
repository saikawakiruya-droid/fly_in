"""The scheduler's plans for later turns: positions, moves, room, evictions.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* PositionBoard: where every drone will be, as a turn's moves are decided.
* ReservationTable: who enters which zone on which turn, planned ahead.
* TurnLedger: room left in zones and connections, this turn and later.
* Evictor: makes room in a zone by scheduling its occupants to move on.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import NamedTuple

from engine import DroneStatus, SimulationState
from errors import SimulationError
from pathfinder import Hop
from world import Connection, Zone


# --- PositionBoard ----------------------------------------------------

class Position(NamedTuple):
    """Where a drone will be, and from the end of which turn for sure.

    Attributes:
        zone_name: The zone the drone stands in, or is landing in.
        since_turn: The turn from whose end the drone is surely there.
    """

    zone_name: str
    since_turn: int


class PositionBoard:
    """The position of every drone on the map while a turn is planned.

    It starts from the state and follows each move the scheduler records,
    so it always tells where the drones will be after the moves decided so
    far. It also keeps how many drones each zone will hold, so counting the
    drones in a set of zones costs the size of the set, not the number of
    drones.
    """

    def __init__(self) -> None:
        """Start with no drone on the board."""
        self._where: dict[int, Position] = {}
        self._drones_in: dict[str, set[int]] = {}

    @classmethod
    def from_state(cls, state: SimulationState) -> "PositionBoard":
        """Place every drone of the state where it surely is.

        Drones standing in a zone have been there since the end of the
        turn just played; drones in flight are there (in the zone they land
        in) from the end of this turn on.

        Args:
            state: The state at the start of the turn.

        Returns:
            A board holding every undelivered drone.
        """
        board = cls()
        played = state.turn_number
        for drone in state.active_drones():
            if drone.status is DroneStatus.IN_TRANSIT:
                if drone.transit_target is not None:
                    board.place(
                        drone.drone_id, drone.transit_target, played + 1
                    )
            elif drone.current_zone is not None:
                board.place(drone.drone_id, drone.current_zone, played)
        return board

    def place(self, drone_id: int, zone_name: str, since_turn: int) -> None:
        """Put the drone in ``zone_name`` from the end of ``since_turn`` on.

        Args:
            drone_id: The drone to place.
            zone_name: The zone it will be in.
            since_turn: The turn from whose end it is surely there.
        """
        old = self._where.get(drone_id)
        if old is not None:
            self._drones_in[old.zone_name].discard(drone_id)
        self._where[drone_id] = Position(zone_name, since_turn)
        self._drones_in.setdefault(zone_name, set()).add(drone_id)

    def where(self, drone_id: int) -> Position:
        """Return the drone's position.

        Args:
            drone_id: The drone to look up.

        Returns:
            Its zone and the turn since which it is there.

        Raises:
            KeyError: If the drone is not on the board.
        """
        return self._where[drone_id]

    def zone_name_by_drone(self) -> dict[int, str]:
        """Return the zone of every drone on the board.

        Returns:
            The zone name by drone_id.
        """
        return {
            drone_id: pos.zone_name for drone_id, pos in self._where.items()
        }

    def drones_in(self, zone_name: str) -> list[int]:
        """Return the drones in the zone, lowest number first.

        Args:
            zone_name: Name of the zone.

        Returns:
            The drone_ids in the zone (empty if none).
        """
        return sorted(self._drones_in.get(zone_name, ()))

    def count_in(self, zone_names: Iterable[str]) -> int:
        """Return how many drones the given zones hold together.

        Args:
            zone_names: The zone names to count.

        Returns:
            The total number of drones in them.
        """
        return sum(
            len(self._drones_in.get(zone_name, ())) for zone_name in zone_names
        )


# --- ReservationTable -------------------------------------------------

@dataclass(frozen=True)
class Reservation:
    """One planned move: a drone leaves a zone and enters an adjacent one.

    A move into a restricted zone takes two turns: the drone departs on
    ``depart_turn`` and enters on ``arrive_turn = depart_turn + 1``. Any
    other move has ``arrive_turn == depart_turn``.

    Attributes:
        drone_id: Which drone moves.
        from_zone: The zone it leaves.
        to_zone: The zone it enters.
        depart_turn: The turn it leaves ``from_zone`` (and uses the
            connection).
        arrive_turn: The turn it enters ``to_zone``.
    """

    drone_id: int
    from_zone: str
    to_zone: str
    depart_turn: int
    arrive_turn: int


class ReservationTable:
    """The single table of planned moves, keyed by (zone, entry turn).

    It holds two kinds of moves:

    * landings: drones in flight toward a restricted zone enter it on the
      next turn. They are reloaded from the state at the start of every
      turn (``start_turn``), so the table also works when it is handed a
      state it did not plan.
    * evictions: a drone standing in a zone is scheduled to move on at a
      given turn, to make room for a drone that will enter that zone.

    The table only counts; it does not know the zones' capacities or the
    connections. Every change is logged, so a failed attempt can be undone
    with ``mark`` and ``rollback``.
    """

    def __init__(self) -> None:
        """Start with an empty table."""
        self._entries: dict[tuple[str, int], list[Reservation]] = {}
        self._leaving: dict[tuple[str, int], int] = {}
        self._departing: dict[int, list[Reservation]] = {}
        self._by_drone: dict[int, list[Reservation]] = {}
        self._log: list[tuple[bool, Reservation]] = []

    def start_turn(self, state: SimulationState) -> None:
        """Prepare the table for planning the state's next turn.

        Moves that departed before that turn are forgotten (they have been
        played), and so are moves whose drone is neither in nor landing in
        the zone it was to leave (the state was changed elsewhere). The drones
        in flight are then loaded as landings for this turn. The undo log
        is cleared.

        Args:
            state: The state whose next turn is about to be planned.
        """
        turn = state.turn_number + 1
        for reservation in self._all():
            if reservation.depart_turn < turn or not self._still_valid(
                state, reservation
            ):
                self._discard(reservation)
        for reservation in landings(state):
            self._insert(reservation)
        self._log.clear()

    def reserve(self, reservation: Reservation) -> None:
        """Add a move to the table.

        Args:
            reservation: The move to add.
        """
        self._insert(reservation)
        self._log.append((True, reservation))

    def remove(self, drone_id: int) -> list[Reservation]:
        """Remove the drone's planned moves and return them.

        Args:
            drone_id: The drone whose moves are removed.

        Returns:
            The removed moves (empty if it had none).
        """
        removed = list(self._by_drone.get(drone_id, []))
        for reservation in removed:
            self._discard(reservation)
            self._log.append((False, reservation))
        return removed

    def leaves_after(self, drone_id: int, turn: int) -> bool:
        """Return whether the drone has a move planned after that turn.

        Args:
            drone_id: The drone to look at.
            turn: The turn after which to look.

        Returns:
            True if one of its moves departs after ``turn``.
        """
        return any(
            reservation.depart_turn > turn
            for reservation in self._by_drone.get(drone_id, [])
        )

    def entering(self, zone_name: str, turn: int) -> int:
        """Return how many drones are planned to enter the zone that turn.

        Args:
            zone_name: Name of the zone.
            turn: The turn of entry.

        Returns:
            The number of planned entries.
        """
        return len(self._entries.get((zone_name, turn), []))

    def leaving(self, zone_name: str, turn: int) -> int:
        """Return how many drones are planned to leave the zone that turn.

        Args:
            zone_name: Name of the zone.
            turn: The turn of departure.

        Returns:
            The number of planned departures.
        """
        return self._leaving.get((zone_name, turn), 0)

    def due(self, turn: int) -> list[Reservation]:
        """Return the moves departing on that turn, in drone_id order.

        Args:
            turn: The turn of departure.

        Returns:
            The moves leaving their zone on ``turn``.
        """
        return sorted(
            self._departing.get(turn, []), key=lambda r: r.drone_id
        )

    def last_turn(self) -> int:
        """Return the latest turn any planned move happens on (0 if none).

        Returns:
            The largest ``arrive_turn`` in the table, or 0.
        """
        return max(
            (reservation.arrive_turn for reservation in self._all()),
            default=0,
        )

    def mark(self) -> int:
        """Return a position to ``rollback`` to.

        Returns:
            The current length of the undo log.
        """
        return len(self._log)

    def rollback(self, mark: int) -> None:
        """Undo every ``reserve`` and ``remove`` made since ``mark``.

        Args:
            mark: A position returned by ``mark``.
        """
        while len(self._log) > mark:
            added, reservation = self._log.pop()
            if added:
                self._discard(reservation)
            else:
                self._insert(reservation)

    def clear(self) -> None:
        """Forget every planned move and the undo log."""
        for reservation in self._all():
            self._discard(reservation)
        self._log.clear()

    def _all(self) -> list[Reservation]:
        """Return every planned move.

        Returns:
            All the moves in the table, grouped by drone.
        """
        return [
            reservation
            for reservations in self._by_drone.values()
            for reservation in reservations
        ]

    @staticmethod
    def _still_valid(state: SimulationState, reservation: Reservation) -> bool:
        """Return whether the drone is still in or landing in its from_zone.

        Args:
            state: The current state.
            reservation: The planned move to check.

        Returns:
            True if the move can still be played from the drone's place.
        """
        drone = state.drones.get(reservation.drone_id)
        if drone is None:
            return False
        if drone.status is DroneStatus.IN_TRANSIT:
            return drone.transit_target == reservation.from_zone
        return (
            drone.status is DroneStatus.AT_ZONE
            and drone.current_zone == reservation.from_zone
        )

    def _insert(self, reservation: Reservation) -> None:
        """Add a move to every index, without logging it.

        Args:
            reservation: The move to add.
        """
        key = (reservation.to_zone, reservation.arrive_turn)
        self._entries.setdefault(key, []).append(reservation)
        leave = (reservation.from_zone, reservation.depart_turn)
        self._leaving[leave] = self._leaving.get(leave, 0) + 1
        self._departing.setdefault(reservation.depart_turn, []).append(
            reservation
        )
        self._by_drone.setdefault(reservation.drone_id, []).append(
            reservation
        )

    def _discard(self, reservation: Reservation) -> None:
        """Remove a move from every index, without logging it.

        Args:
            reservation: The move to remove; it must be in the table.
        """
        key = (reservation.to_zone, reservation.arrive_turn)
        self._entries[key].remove(reservation)
        if not self._entries[key]:
            del self._entries[key]
        leave = (reservation.from_zone, reservation.depart_turn)
        self._leaving[leave] -= 1
        if not self._leaving[leave]:
            del self._leaving[leave]
        departing = self._departing[reservation.depart_turn]
        departing.remove(reservation)
        if not departing:
            del self._departing[reservation.depart_turn]
        reservations = self._by_drone[reservation.drone_id]
        reservations.remove(reservation)
        if not reservations:
            del self._by_drone[reservation.drone_id]


def landings(state: SimulationState) -> list[Reservation]:
    """Return the landings of the state's next turn, as planned moves.

    Every drone in flight toward a restricted zone departed on the turn
    just played and enters its zone on the next one.

    Args:
        state: The state after the turn just played.

    Returns:
        One move per drone in flight, departing on the turn just played.

    Raises:
        SimulationError: If a drone in flight has no route recorded.
    """
    turn = state.turn_number + 1
    result: list[Reservation] = []
    for drone in state.drones_in_transit():
        target = drone.transit_target
        link = drone.in_transit_connection
        if target is None or link is None:
            raise SimulationError(
                f"drone D{drone.drone_id} is in flight without a route"
            )
        source = state.network.connection_named(target, link).other_end(
            target
        )
        result.append(
            Reservation(drone.drone_id, source, target, turn - 1, turn)
        )
    return result


# --- TurnLedger -------------------------------------------------------

class TurnLedger:
    """Counts the room left in zones and connections while a turn is planned.

    The scheduler creates one ledger per turn: the ``planning_turn``, the
    one after the state's ``turn_number`` (the turns already played). It
    asks the ledger before giving each order and calls ``record`` after
    giving it. It counts, by the resolver's rules:

    * this turn's orders recorded so far: a drone leaves its zone this
      turn, and enters the next zone this turn, or on the next turn if that
      zone is restricted (it is on the connection at the end of this turn);
    * the planned moves of the ``ReservationTable``: drones landing this
      turn, and drones scheduled to leave a zone on a later turn.

    A zone's *projected* load on a turn T is the drones standing in it now,
    plus every planned or recorded entry up to T, minus every departure up
    to T. Drones that stand in a zone without a planned departure are
    counted as staying there for good. A zone has a *seat* on turn T if one
    more drone ``fits`` on top of its projected load; the start and end
    zones always have seats.

    A connection is used on the turn a drone departs across it, in either
    direction; drones landing through it this turn leave it, so they take
    none of its capacity.

    Only the orders recorded so far are counted. Later orders can only add
    departures, which free more room, or entries, which are checked again,
    so every order allowed here is still legal for the whole turn.
    """

    def __init__(
        self, state: SimulationState, table: ReservationTable | None = None
    ) -> None:
        """Start an empty ledger over the state at the start of a turn.

        Args:
            state: The state before the turn.
            table: The planned moves, already prepared for this turn with
                ``ReservationTable.start_turn``. Without one, a table holding
                only this turn's landings is used.
        """
        self.state = state
        self.planning_turn = state.turn_number + 1
        if table is None:
            table = ReservationTable()
            table.start_turn(state)
        self._table = table
        self._zone_change: dict[tuple[str, int], int] = {}
        self._link_use: dict[str, int] = {}

    def arrival_turn(self, zone: Zone) -> int:
        """Return the turn a drone ordered into the zone now would enter it.

        Args:
            zone: The zone to enter.

        Returns:
            The planning turn, or the one after it for a restricted zone.
        """
        return zone.arrival_turn(self.planning_turn)

    def link_free(self, connection: Connection, turn: int) -> bool:
        """Return whether one more drone can depart across it on that turn.

        Args:
            connection: The connection to depart across.
            turn: The turn of departure.

        Returns:
            True if its departures that turn are below its capacity.
        """
        used = sum(
            1 for reservation in self._table.due(turn)
            if connection.involves(reservation.from_zone)
            and connection.involves(reservation.to_zone)
        )
        if turn == self.planning_turn:
            used += self._link_use.get(connection.name, 0)
        return used < connection.max_link_capacity

    def has_seat_from(self, zone: Zone, first_turn: int) -> bool:
        """Return whether the zone has a seat on every turn from first_turn.

        Only turns up to ``horizon`` need checking: no load changes later.

        Args:
            zone: The zone to look at.
            first_turn: The first turn the seat is needed.

        Returns:
            True if one more drone fits on every turn from ``first_turn``.
        """
        return all(
            self.fits(zone, turn, 1)
            for turn in range(first_turn, max(first_turn, self.horizon()) + 1)
        )

    def fits(self, zone: Zone, turn: int, extra: int) -> bool:
        """Return whether ``extra`` more drones fit in the zone that turn.

        Args:
            zone: The zone to look at.
            turn: The turn to check.
            extra: The number of drones to add.

        Returns:
            True if they fit (always for a zone without a capacity).
        """
        capacity = zone.capacity
        if capacity is None:
            return True
        return self.projected_load(zone.name, turn) + extra <= capacity

    def projected_load(self, zone_name: str, turn: int) -> int:
        """Return the zone's projected load at the end of that turn.

        Args:
            zone_name: Name of the zone.
            turn: The turn to look at.

        Returns:
            The drones in it now, plus entries, minus departures up to
            ``turn``.
        """
        load = self.state.occupancy(zone_name)
        for step in range(self.planning_turn, turn + 1):
            load += (
                self._table.entering(zone_name, step)
                - self._table.leaving(zone_name, step)
                + self._zone_change.get((zone_name, step), 0)
            )
        return load

    def horizon(self) -> int:
        """Return the last turn on which any counted load changes.

        Returns:
            The table's last turn, and at least the turn after this one.
        """
        return max(self._table.last_turn(), self.planning_turn + 1)

    def record(self, from_zone: str, hop: Hop) -> None:
        """Count an order moving a drone from ``from_zone`` along ``hop``.

        Args:
            from_zone: The zone the drone leaves.
            hop: The connection and zone it moves to.
        """
        self._count(from_zone, hop, 1)

    def cancel(self, from_zone: str, hop: Hop) -> None:
        """Undo a ``record`` of the same order.

        Args:
            from_zone: The zone the drone was to leave.
            hop: The connection and zone it was to move to.
        """
        self._count(from_zone, hop, -1)

    def _count(self, from_zone: str, hop: Hop, sign: int) -> None:
        """Add (sign 1) or take back (sign -1) one order's counts.

        Args:
            from_zone: The zone the drone leaves.
            hop: The connection and zone it moves to.
            sign: 1 to record the order, -1 to cancel it.
        """
        self._add(self._zone_change, (from_zone, self.planning_turn), -sign)
        self._add(
            self._zone_change,
            (hop.zone.name, self.arrival_turn(hop.zone)),
            sign,
        )
        name = hop.connection.name
        self._link_use[name] = self._link_use.get(name, 0) + sign

    @staticmethod
    def _add(counts: dict[tuple[str, int], int], key: tuple[str, int],
             delta: int) -> None:
        """Add ``delta`` to a count.

        Args:
            counts: The counts to change.
            key: The zone name and turn.
            delta: The amount to add (negative to subtract).
        """
        counts[key] = counts.get(key, 0) + delta


# --- Evictor ----------------------------------------------------------

class Evictor:
    """Plans evictions for one turn: occupants leave on a given later turn.

    An eviction is an ordinary planned move written to the
    ``ReservationTable``: drone X leaves zone Z on turn T, along one of
    ``Pathfinder.next_hops(Z)`` (shortest moves only), into zone W. It is
    planned only if, on turn T, the connection Z-W has room for it, and W
    has a seat for X from the turn X enters it (T, or T + 1 if W is
    restricted) on. If W has no seat, one of W's occupants is evicted the
    same way, recursively. Every step lowers the distance to the end zone,
    so the recursion always ends; the end zone always has room.

    If an attempt fails, every move it planned is undone, so the table is
    left as it was.
    """

    def __init__(
        self,
        ledger: TurnLedger,
        table: ReservationTable,
        hops: Mapping[str, list[Hop]],
        board: PositionBoard,
    ) -> None:
        """Plan evictions over this turn's ledger.

        Args:
            ledger: This turn's counts.
            table: The table the ledger counts; it receives the evictions.
            hops: The shortest next hops of every zone.
            board: Where every drone still on the map will be after
                this turn's moves. Kept up to date by the scheduler.
        """
        self.ledger = ledger
        self.table = table
        self.hops = hops
        self.board = board

    def make_room(self, zone: Zone, first_turn: int, extra: int) -> bool:
        """Evict occupants until ``extra`` more drones fit in the zone.

        The zone must fit them on ``first_turn`` and every later turn with a
        planned move. The evictions found are written to the table.

        Args:
            zone: The zone to make room in.
            first_turn: The first turn the room is needed.
            extra: How many more drones must fit.

        Returns:
            Whether enough room was made. If not, the table is unchanged.
        """
        mark = self.table.mark()
        if self._keep_seats(zone, first_turn, extra):
            return True
        self.table.rollback(mark)
        return False

    def _keep_seats(self, zone: Zone, first_turn: int, extra: int) -> bool:
        """Evict until ``extra`` more drones fit on every turn from first_turn.

        This ends: the planned moves reach only a few turns ahead (the
        horizon), and each eviction moves a drone into a zone strictly
        closer to the end zone, so the recursion goes at most as deep as
        the distance to the end zone, which always has room.

        Args:
            zone: The zone to make room in.
            first_turn: The first turn the room is needed.
            extra: How many more drones must fit.

        Returns:
            Whether enough room was made (the table may be half changed
            if not; ``make_room`` rolls it back).
        """
        turn = first_turn
        while turn <= max(first_turn, self.ledger.horizon()):
            while not self.ledger.fits(zone, turn, extra):
                if not self._evict_one(zone, turn):
                    return False
            turn += 1
        return True

    def _evict_one(self, zone: Zone, turn: int) -> bool:
        """Plan one occupant of the zone to leave it on that turn.

        Args:
            zone: The zone to evict from.
            turn: The turn the occupant leaves.

        Returns:
            Whether an eviction was planned.
        """
        drone_id = self._candidate(zone.name, turn)
        if drone_id is None:
            return False
        for hop in self.hops.get(zone.name, []):
            if not self.ledger.link_free(hop.connection, turn):
                continue
            arrive_turn = hop.zone.arrival_turn(turn)
            mark = self.table.mark()
            if not self._keep_seats(hop.zone, arrive_turn, 1):
                self.table.rollback(mark)
                continue
            self.table.reserve(
                Reservation(
                    drone_id, zone.name, hop.zone.name, turn, arrive_turn
                )
            )
            return True
        return False

    def _candidate(self, zone_name: str, turn: int) -> int | None:
        """Return the lowest-numbered drone that can be evicted on that turn.

        It must surely be in the zone at the end of the turn before, and have
        no planned move after this turn (it is not already leaving). Trying
        one drone is enough: all of them would take the same hops.

        Args:
            zone_name: Name of the zone to evict from.
            turn: The turn the drone would leave.

        Returns:
            The drone's id, or None if no drone can be evicted.
        """
        now = self.ledger.planning_turn
        for drone_id in self.board.drones_in(zone_name):
            if self.board.where(drone_id).since_turn > turn - 1:
                continue
            if self.table.leaves_after(drone_id, now):
                continue
            return drone_id
        return None
