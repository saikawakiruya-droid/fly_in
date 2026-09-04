"""SimulationState: the mutable per-turn state of the whole simulation."""

from dataclasses import dataclass, field

from ..models.drone import Drone


@dataclass
class Move:
    """One drone's action during a single turn.

    Attributes:
        drone_id: Which drone moved.
        destination: Target zone name, or the connection name if the drone
            just entered a restricted-zone transit.
    """

    drone_id: int
    destination: str


@dataclass
class SimulationState:
    """Everything needed to decide and validate the next turn.

    Attributes:
        turn_number: 1-based index of the current turn.
        drones: All drones, keyed by drone_id.
        zone_occupancy: Current drone count per zone name.
        connection_usage: Current drone count per connection name.
    """

    turn_number: int = 0
    drones: dict[int, Drone] = field(default_factory=dict)
    zone_occupancy: dict[str, int] = field(default_factory=dict)
    connection_usage: dict[str, int] = field(default_factory=dict)

    def apply_moves(self, moves: list[Move]) -> None:
        """Apply a batch of simultaneous moves, updating occupancy counts."""
        raise NotImplementedError

    @property
    def is_complete(self) -> bool:
        """Return whether every drone has reached the end zone."""
        raise NotImplementedError
