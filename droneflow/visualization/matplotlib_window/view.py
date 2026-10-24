"""MatplotlibWindowVisualizer: the run shown turn by turn in a window.

The window holds a ``MapScene`` and the key to its colors.
"""

import time

import matplotlib.pyplot as plt

from ...errors import VisualizationError
from ...models.network import Network
from ...simulation.state import Move, SimulationState
from .scene import BACKGROUND, KEY, TEXT, MapScene

DELAY = 0.5
"""Seconds each turn stays on screen."""
_TICK = 0.02
"""Seconds between two looks at the window's events while waiting."""


class MatplotlibWindowVisualizer:
    """Shows the run in a matplotlib window, one turn every ``delay``.

    The window opens when the view is made. Closing it stops the drawing
    and the waiting; the simulation then finishes at once, so the turn
    log is still complete. After a finished run the window stays open
    until it is closed.

    Attributes:
        figure: The window's figure.
        scene: The network drawn in it.
        delay: Seconds each turn stays on screen.
    """

    def __init__(self, network: Network, delay: float = DELAY) -> None:
        """Open the window and draw the network.

        Args:
            network: The network to draw.
            delay: Seconds each turn stays on screen.

        Raises:
            VisualizationError: If matplotlib cannot show a window (for
                example when there is no display).
        """
        figure = plt.figure("Fly-in", figsize=(10, 7),
                            facecolor=BACKGROUND)
        if figure.canvas.required_interactive_framework is None:
            plt.close(figure)
            raise VisualizationError(
                "cannot open the matplotlib window (no display?)"
            )
        figure.text(0.02, 0.02, KEY, color=TEXT, fontsize=8)
        self.figure = figure
        self.scene = MapScene(figure.add_axes((0.02, 0.06, 0.96, 0.88)),
                              network)
        self.delay = delay
        self._finished = False
        figure.show()

    @property
    def is_open(self) -> bool:
        """Return whether the window is still on screen."""
        return plt.fignum_exists(self.figure.number)

    def begin(self, state: SimulationState) -> None:
        """Show the initial state.

        Args:
            state: The state before the first turn.
        """
        self._show(state)

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Show the state after a turn.

        Args:
            state: The state after the turn.
            moves: The moves of the turn (not drawn).
        """
        self._show(state)

    def close(self) -> None:
        """Keep a finished run on screen until closed, then close."""
        if self._finished and self.is_open:
            plt.show()
        plt.close(self.figure)

    def _show(self, state: SimulationState) -> None:
        """Draw a state, then wait ``delay`` while handling the window.

        Nothing is drawn once the window is closed.

        Args:
            state: The state to draw.
        """
        if not self.is_open:
            return
        self.scene.show(state)
        self._finished = state.is_complete
        canvas = self.figure.canvas
        canvas.draw_idle()
        deadline = time.monotonic() + self.delay
        while self.is_open and time.monotonic() < deadline:
            canvas.start_event_loop(_TICK)
