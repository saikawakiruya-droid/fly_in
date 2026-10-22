"""TurnLogPrinter: writes the turn log line by line while the run goes on."""

import sys
from typing import TextIO

from ..simulation.state import Move, SimulationState
from .formatter import TurnLogFormatter


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
        """Write nothing: turn 0 has no moves."""

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Write the turn's line and flush it right away."""
        if not moves:
            return
        self.stream.write(self.formatter.format_turn(moves) + "\n")
        self.stream.flush()

    def close(self) -> None:
        """Flush the stream; it is not closed (it is not ours)."""
        self.stream.flush()
