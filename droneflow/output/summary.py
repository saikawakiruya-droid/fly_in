"""RunSummary: the headline numbers of a finished simulation."""

from dataclasses import dataclass

from ..simulation.state import Move


@dataclass(frozen=True)
class RunSummary:
    """Total turns plus two of the subject's secondary metrics (VII.6).

    Attributes:
        total_turns: Total number of simulation turns (the main score).
        nb_drones: Number of drones routed.
        average_turns_per_drone: Mean of the turn on which each drone
            was delivered.
        moves_per_turn: Mean number of moves (log entries) per turn.
    """

    total_turns: int
    nb_drones: int
    average_turns_per_drone: float
    moves_per_turn: float

    @classmethod
    def from_turns(
        cls, turns: list[list[Move]], nb_drones: int
    ) -> "RunSummary":
        """Compute the summary of a completed run.

        A drone's last move is always its arrival in the end zone, so
        the turn of its last appearance is its delivery turn.

        Args:
            turns: Every turn's moves, as returned by the engine.
            nb_drones: Number of drones in the run.

        Returns:
            The summary.
        """
        delivered_on: dict[int, int] = {}
        for number, moves in enumerate(turns, start=1):
            for move in moves:
                delivered_on[move.drone_id] = number
        total_moves = sum(len(moves) for moves in turns)
        return cls(
            total_turns=len(turns),
            nb_drones=nb_drones,
            average_turns_per_drone=(
                sum(delivered_on.values()) / nb_drones if nb_drones else 0.0
            ),
            moves_per_turn=total_moves / len(turns) if turns else 0.0,
        )

    def describe(self) -> str:
        """Return the summary as one human readable line.

        Returns:
            The line, starting with ``summary:`` (no newline).
        """
        return (
            f"summary: {self.total_turns} turns, {self.nb_drones} drones, "
            f"{self.average_turns_per_drone:.2f} turns per drone "
            f"on average, {self.moves_per_turn:.2f} moves per turn"
        )
