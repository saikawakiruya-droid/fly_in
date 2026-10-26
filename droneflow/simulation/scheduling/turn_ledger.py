"""TurnLedger: room left in zones and connections, this turn and later."""

from ...models.connection import Connection
from ...models.zone import Zone
from ...pathfinding.pathfinder import Hop
from .reservation_table import ReservationTable
from ..state import SimulationState


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
