"""TurnLogFormatter: prints turns in the ``D<ID>-<zone>`` format."""

from ..simulation.state import Move


class TurnLogFormatter:
    """Formats and prints simulation turns in the required output format."""

    def format_turn(self, moves: list[Move]) -> str:
        """Format a single turn's moves as one space-separated line."""
        raise NotImplementedError

    def emit(self, turns: list[list[Move]]) -> None:
        """Print every turn, one line each, in order.

        Turns with no moves (nothing happened) are skipped per the subject's
        output format, which only lists drones that moved.
        """
        raise NotImplementedError
