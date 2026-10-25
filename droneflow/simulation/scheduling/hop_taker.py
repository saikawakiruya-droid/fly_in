"""HopTaker: takes the first hop a drone can make this turn, and records it."""

from ...models.zone import ZoneType
from ...pathfinding.pathfinder import Hop
from .evictor import Evictor
from .positions import PositionBoard
from .turn_ledger import TurnLedger


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
        self, drone_id: int, here: str, hops: list[Hop]
    ) -> Hop | None:
        """Take the first of ``hops`` the drone can make, or return None.

        Args:
            drone_id: The drone to move.
            here: The zone it stands in.
            hops: The hops to try, in order.

        Returns:
            The hop taken, or None if none can be made, even by evicting.
        """
        for may_evict in (False, True):
            for hop in hops:
                if self._take(drone_id, here, hop, may_evict):
                    return hop
        return None

    def _take(
        self, drone_id: int, here: str, hop: Hop, may_evict: bool
    ) -> bool:
        """Take ``hop`` if it can be made; return whether it was taken.

        Args:
            drone_id: The drone to move.
            here: The zone it stands in.
            hop: The hop to try.
            may_evict: Whether the ``Evictor`` may make room.

        Returns:
            True if the hop was taken and recorded.
        """
        turn = self.ledger.planning_turn
        if not self.ledger.link_free(hop.connection, turn):
            return False
        arrive = self.ledger.arrival_turn(hop.zone)
        if self.ledger.has_seat_from(hop.zone, arrive):
            self._record(drone_id, here, hop, arrive)
            return True
        if not may_evict:
            return False
        if hop.zone.zone_type is ZoneType.RESTRICTED:
            return self._land_after_evicting(drone_id, here, hop, arrive)
        return self._enter_then_evict(drone_id, here, hop, arrive)

    def _land_after_evicting(
        self, drone_id: int, here: str, hop: Hop, arrive: int
    ) -> bool:
        """Fly to a full restricted zone if occupants can leave in time.

        The drone must land on ``arrive`` (it cannot wait on the
        connection), so the zone needs one more seat (``extra=1``) from
        that turn on.

        Args:
            drone_id: The drone to move.
            here: The zone it stands in.
            hop: The hop into the restricted zone.
            arrive: The turn it lands.

        Returns:
            True if room was made and the hop recorded.
        """
        if not self.evictor.make_room(hop.zone, arrive, 1):
            return False
        self._record(drone_id, here, hop, arrive)
        return True

    def _enter_then_evict(
        self, drone_id: int, here: str, hop: Hop, arrive: int
    ) -> bool:
        """Enter a zone whose seat is kept for a later drone, then evict.

        The zone has room now but not on a later turn, because a drone is
        planned to enter it then. The drone enters first, so it is already
        counted; the zone then needs no extra seat (``extra=0``) from the
        next turn on, and its occupants (this drone included) are evicted
        until it fits. If that fails, the move is undone.

        Args:
            drone_id: The drone to move.
            here: The zone it stands in.
            hop: The hop into the zone.
            arrive: The turn it enters the zone.

        Returns:
            True if the hop was recorded and room made; False if undone.
        """
        if not self.ledger.fits(hop.zone, arrive, 1):
            return False
        before = self.board.where(drone_id)
        self._record(drone_id, here, hop, arrive)
        if self.evictor.make_room(hop.zone, arrive + 1, 0):
            return True
        self.ledger.cancel(here, hop)
        self.board.place(drone_id, before.zone_name, before.since_turn)
        return False

    def _record(self, drone_id: int, here: str, hop: Hop, arrive: int) -> None:
        """Record the hop in the ledger and move the drone on the board.

        Args:
            drone_id: The drone to move.
            here: The zone it leaves.
            hop: The hop it takes.
            arrive: The turn it enters the hop's zone.
        """
        self.ledger.record(here, hop)
        self.board.place(drone_id, hop.zone.name, arrive)
