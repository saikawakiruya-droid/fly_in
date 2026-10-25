"""ReservationTable: who enters which zone on which turn, planned ahead."""

from dataclasses import dataclass

from ...errors import SimulationError
from ...models.drone import DroneStatus
from ..state import SimulationState


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
