"""Evictor: makes room in a zone by scheduling its occupants to move on."""

from collections.abc import Mapping

from ...models.zone import Zone
from ...pathfinding.pathfinder import Hop
from .positions import PositionBoard
from .reservation_table import Reservation, ReservationTable
from .turn_ledger import TurnLedger


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
