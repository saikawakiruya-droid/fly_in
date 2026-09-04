"""Application: orchestrates parsing, pathfinding, simulation, and output."""

from .cli import Args
from .visualization.base import Visualizer


class Application:
    """Wires together every stage of the pipeline for a single run."""

    def __init__(self, args: Args) -> None:
        self.args = args

    def run(self) -> None:
        """Parse the map, simulate it, and print the turn log.

        Raises:
            droneflow.errors.FlyInError: On any parse or simulation failure.
        """
        raise NotImplementedError

    def _make_visualizer(self) -> Visualizer | None:
        """Build the visualizer selected by --visual, or None for "none"."""
        raise NotImplementedError
