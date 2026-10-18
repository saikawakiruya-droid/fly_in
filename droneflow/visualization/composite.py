"""CompositeVisualizer: show the same run in several views at once."""

from collections.abc import Sequence

from ..simulation.state import Move, SimulationState
from .base import Visualizer


class CompositeVisualizer:
    """Forwards every call to each of its views, in order.

    Used for ``--visual=both`` (terminal and graphical together).
    """

    def __init__(self, views: Sequence[Visualizer]) -> None:
        """Keep the views to forward to."""
        self.views: list[Visualizer] = list(views)

    def begin(self, state: SimulationState) -> None:
        """Show the initial state in every view."""
        for view in self.views:
            view.begin(state)

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Show the turn in every view."""
        for view in self.views:
            view.render(state, moves)

    def close(self) -> None:
        """Close every view, even if closing one of them fails.

        Views are closed in order. If several fail, the last failure is
        raised, with the earlier ones chained to it as context.
        """
        self._close_from(0)

    def _close_from(self, index: int) -> None:
        """Close views[index:]; ``finally`` chains failures as context."""
        if index >= len(self.views):
            return
        try:
            self.views[index].close()
        finally:
            self._close_from(index + 1)
