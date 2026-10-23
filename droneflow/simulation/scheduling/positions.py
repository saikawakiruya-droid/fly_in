"""PositionBoard: where every drone will be, as a turn's moves are decided."""

from collections.abc import Iterable
from typing import NamedTuple

from ...models.drone import DroneStatus
from ..state import SimulationState


class Position(NamedTuple):
    """Where a drone will be, and from the end of which turn for sure.

    Attributes:
        zone: The zone the drone stands in, or is landing in.
        since_turn: The turn from whose end the drone is surely there.
    """

    zone: str
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

    def place(self, drone_id: int, zone: str, since_turn: int) -> None:
        """Put the drone in ``zone`` from the end of ``since_turn`` on.

        Args:
            drone_id: The drone to place.
            zone: The zone it will be in.
            since_turn: The turn from whose end it is surely there.
        """
        old = self._where.get(drone_id)
        if old is not None:
            self._drones_in[old.zone].discard(drone_id)
        self._where[drone_id] = Position(zone, since_turn)
        self._drones_in.setdefault(zone, set()).add(drone_id)

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

    def zone_by_drone(self) -> dict[int, str]:
        """Return the zone of every drone on the board.

        Returns:
            The zone name by drone_id.
        """
        return {drone_id: pos.zone for drone_id, pos in self._where.items()}

    def drones_in(self, zone: str) -> list[int]:
        """Return the drones in the zone, lowest number first.

        Args:
            zone: Name of the zone.

        Returns:
            The drone_ids in the zone (empty if none).
        """
        return sorted(self._drones_in.get(zone, ()))

    def count_in(self, zones: Iterable[str]) -> int:
        """Return how many drones the given zones hold together.

        Args:
            zones: The zone names to count.

        Returns:
            The total number of drones in them.
        """
        return sum(len(self._drones_in.get(zone, ())) for zone in zones)
