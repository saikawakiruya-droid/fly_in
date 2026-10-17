"""Application: orchestrates parsing, pathfinding, simulation, and output."""

import sys
from typing import TextIO

from .cli import Args
from .errors import MapFileError, VisualizationError
from .models.world import World
from .output.summary import RunSummary
from .output.turn_log_view import TurnLogPrinter
from .parsing.map_parser import MapParser
from .pathfinding.pathfinder import Pathfinder
from .simulation.engine import SimulationEngine
from .simulation.scheduler import Scheduler
from .simulation.state import Move, SimulationState
from .visualization.base import Visualizer
from .visualization.composite import CompositeVisualizer
from .visualization.terminal_view import TerminalVisualizer


class _GuardedView:
    """Wraps a view so that a failing ``close`` cannot change the outcome.

    ``begin`` and ``render`` are forwarded as they are. An exception from
    ``close`` is kept in ``error`` instead of being raised: after a
    successful run the turn log is already complete, and after a failed
    run the original error must not be replaced by the close failure.

    Attributes:
        name: Short name of the view, used in warnings.
        error: The exception raised by the view's ``close``, if any.
    """

    def __init__(self, name: str, view: Visualizer) -> None:
        """Wrap ``view``, called ``name`` in warnings."""
        self.name = name
        self.view = view
        self.error: Exception | None = None

    def begin(self, state: SimulationState) -> None:
        """Forward to the view."""
        self.view.begin(state)

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Forward to the view."""
        self.view.render(state, moves)

    def close(self) -> None:
        """Close the view, keeping any exception instead of raising it."""
        try:
            self.view.close()
        except Exception as exc:
            self.error = exc


class Application:
    """Wires together every stage of the pipeline for a single run.

    The turn log goes to ``out`` (standard output), one line per turn as
    the run goes on, and nothing else does. The terminal view, warnings
    and the final summary go to ``err`` (standard error).
    """

    def __init__(
        self,
        args: Args,
        out: TextIO | None = None,
        err: TextIO | None = None,
    ) -> None:
        """Keep the arguments and the output streams.

        Args:
            args: The parsed command-line arguments.
            out: Where the turn log goes; defaults to ``sys.stdout``.
            err: Where the terminal view, warnings and the summary go;
                defaults to ``sys.stderr``.
        """
        self.args = args
        self.out: TextIO = sys.stdout if out is None else out
        self.err: TextIO = sys.stderr if err is None else err

    def run(self) -> None:
        """Parse the map, simulate it, and print the turn log.

        Raises:
            droneflow.errors.FlyInError: On any failure: the map file
                cannot be read (``MapFileError``) or is invalid
                (``ParseError``), the goal is unreachable
                (``UnreachableGoalError``), the requested view cannot be
                used (``VisualizationError``), or the simulation fails
                (``SimulationError``).
        """
        world = self._load_world()
        pathfinder = Pathfinder(world.network)
        engine = SimulationEngine(
            world, Scheduler(world.network, pathfinder)
        )
        views = self._make_views()
        printer = TurnLogPrinter(self.out)
        try:
            turns = engine.run(CompositeVisualizer([printer, *views]))
        finally:
            self._warn_close_failures(views)
        self.err.write(
            RunSummary.from_turns(turns, world.nb_drones).describe() + "\n"
        )
        self.err.flush()

    def _load_world(self) -> World:
        """Parse the map file.

        Raises:
            MapFileError: If the file cannot be opened or is not UTF-8
                text.
            droneflow.errors.ParseError: If the map is invalid.
        """
        path = self.args.map_path
        try:
            return MapParser(path).parse()
        except OSError as exc:
            reason = exc.strerror or type(exc).__name__
            raise MapFileError(str(path), reason) from exc
        except UnicodeDecodeError as exc:
            raise MapFileError(str(path), "not UTF-8 text") from exc

    def _make_views(self) -> list[_GuardedView]:
        """Build the views selected by --visual and --step.

        With ``both``, only the graphical window waits for the user in
        step mode; the terminal view just follows it.

        Raises:
            VisualizationError: If the graphical view is requested but
                pygame is not installed.
        """
        visual = self.args.visual
        views: list[_GuardedView] = []
        if visual in ("terminal", "both"):
            terminal_steps = self.args.step and visual == "terminal"
            views.append(_GuardedView(
                "terminal",
                TerminalVisualizer(stream=self.err, step=terminal_steps),
            ))
        if visual in ("graphical", "both"):
            views.append(_GuardedView("graphical", self._graphical_view()))
        return views

    def _graphical_view(self) -> Visualizer:
        """Import pygame lazily and build the graphical view.

        Raises:
            VisualizationError: If pygame is not installed.
        """
        try:
            from .visualization.graphical_view import GraphicalVisualizer
        except ModuleNotFoundError as exc:
            if exc.name is None or exc.name.split(".")[0] != "pygame":
                raise
            raise VisualizationError(
                "the graphical view needs pygame (pygame-ce): run "
                "'make install' or 'pip install pygame-ce', or use "
                "--visual terminal"
            ) from exc
        return GraphicalVisualizer(
            delay=self.args.delay, hold_final=True, step=self.args.step
        )

    def _warn_close_failures(self, views: list[_GuardedView]) -> None:
        """Write one warning line per view whose ``close`` failed."""
        for view in views:
            if view.error is not None:
                self.err.write(
                    f"warning: could not close the {view.name} view: "
                    f"{view.error}\n"
                )
        self.err.flush()
