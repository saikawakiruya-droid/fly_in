"""Evictor: makes room in a zone by scheduling its occupants to move on."""

from collections.abc import Mapping

from ..models.zone import Zone, ZoneType
from ..pathfinding.pathfinder import Hop
from .positions import PositionBoard
from .reservation_table import Reservation
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
        hops: Mapping[str, list[Hop]],
        positions: PositionBoard,
    ) -> None:
        """Plan evictions over this turn's ledger.

        Args:
            ledger: This turn's counts; its table receives the evictions.
            hops: The shortest next hops of every zone.
            positions: Where every drone still on the map will be after
                this turn's moves. Kept up to date by the scheduler.
        """
        self.ledger = ledger
        self.table = ledger.table
        self.hops = hops
        self.positions = positions

    def make_room(self, zone: Zone, first_turn: int, extra: int) -> bool:
        """Evict occupants until ``extra`` more drones fit in the zone.

        The zone must fit them on ``first_turn`` and every later turn with a
        planned move. The evictions found are written to the table.

        Returns:
            Whether enough room was made. If not, the table is unchanged.
        """
        mark = self.table.mark()
        if self._keep_seats(zone, first_turn, extra):
            return True
        self.table.rollback(mark)
        return False

    def _keep_seats(self, zone: Zone, first_turn: int, extra: int) -> bool:
        turn = first_turn
        while turn <= max(first_turn, self.ledger.horizon()):
            while not self.ledger.has_seat(zone, turn, extra):
                if not self._evict_one(zone, turn):
                    return False
            turn += 1
        return True

    def _evict_one(self, zone: Zone, turn: int) -> bool:
        """Plan one occupant of the zone to leave it on that turn."""
        drone_id = self._candidate(zone.name, turn)
        if drone_id is None:
            return False
        for hop in self.hops.get(zone.name, []):
            if not self.ledger.link_free(hop.connection, turn):
                continue
            arrive = turn
            if hop.zone.zone_type is ZoneType.RESTRICTED:
                arrive = turn + 1
            mark = self.table.mark()
            if not self._keep_seats(hop.zone, arrive, 1):
                self.table.rollback(mark)
                continue
            self.table.reserve(
                Reservation(drone_id, zone.name, hop.zone.name, turn, arrive)
            )
            return True
        return False

    def _candidate(self, zone_name: str, turn: int) -> int | None:
        """Return the lowest-numbered drone that can be evicted on that turn.

        It must surely be in the zone at the end of the turn before, and have
        no planned move after this turn (it is not already leaving). Trying
        one drone is enough: all of them would take the same hops.
        """
        now = self.ledger.turn
        for drone_id in self.positions.drones_in(zone_name):
            if self.positions.where(drone_id).since_turn > turn - 1:
                continue
            if any(
                move.depart_turn > now
                for move in self.table.planned(drone_id)
            ):
                continue
            return drone_id
        return None
