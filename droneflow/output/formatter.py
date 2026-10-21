"""TurnLogFormatter: formats a turn in the ``D<ID>-<zone>`` format."""

from ..simulation.state import Move


class TurnLogFormatter:
    """Formats simulation turns in the required output format."""

    def format_turn(self, moves: list[Move]) -> str:
        """Format a single turn's moves as one space-separated line."""
        return " ".join(f"D{m.drone_id}-{m.destination}" for m in moves)
