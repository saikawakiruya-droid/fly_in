"""The turn log on standard output and the run's summary line.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* TurnLogFormatter: formats a turn in the ``D<ID>-<zone>`` format.
* TurnLogPrinter: writes the turn log line by line while the run goes on.
* RunSummary: the headline numbers of a finished simulation.
"""

import sys
from dataclasses import dataclass
from typing import TextIO

from engine import Move, SimulationState


# --- TurnLogFormatter -------------------------------------------------

class TurnLogFormatter:
    """Formats simulation turns in the required output format."""

    def format_turn(self, moves: list[Move]) -> str:
        """Format a single turn's moves as one space-separated line.

        Args:
            moves: The moves made during the turn.

        Returns:
            The line, e.g. ``D1-roof1 D2-corridorA`` (no newline).
        """
        return " ".join(move.text for move in moves)


# --- TurnLogPrinter ---------------------------------------------------

class TurnLogPrinter:
    """Prints each turn in the subject's output format as soon as it ends.

    It has the same ``begin`` / ``render`` / ``close`` shape as a
    ``TurnObserver``, so the engine drives it like any view; the
    formatting itself is delegated to a ``TurnLogFormatter``. Only the
    turn lines are written, so the stream holds exactly the required
    output. Empty turns are skipped (the engine never renders one).
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        """Choose where to write.

        Args:
            stream: Where turn lines go; defaults to ``sys.stdout``.
        """
        self.stream: TextIO = sys.stdout if stream is None else stream
        self.formatter = TurnLogFormatter()

    def begin(self, state: SimulationState) -> None:
        """Write nothing: turn 0 has no moves.

        Args:
            state: The state before the first turn (unused).
        """

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Write the turn's line and flush it right away.

        Args:
            state: The state after the turn (unused).
            moves: The moves made during the turn.
        """
        if not moves:
            return
        self.stream.write(self.formatter.format_turn(moves) + "\n")
        self.stream.flush()

    def close(self) -> None:
        """Flush the stream; it is not closed (it is not ours)."""
        self.stream.flush()


# --- RunSummary -------------------------------------------------------

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
