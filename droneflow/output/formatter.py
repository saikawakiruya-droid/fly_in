"""TurnLogFormatter: formats a turn in the ``D<ID>-<zone>`` format."""

from ..simulation.state import Move


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
