"""Application: orchestrates parsing, pathfinding, simulation, and output."""

import sys
from collections.abc import Callable
from typing import TextIO

from .cli import Args
from .errors import MapFileError, OutputFileError, VisualizationError
from .interchange.run_file import RunRecorder
from .interchange.world_file import WorldFile
from .models.network import Network
from .models.world import World
from .output.summary import RunSummary
from .output.turn_log_printer import TurnLogPrinter
from .parsing.map_parser import MapParser
from .pathfinding.pathfinder import Pathfinder
from .simulation.engine import MoveDecider, SimulationEngine
from .simulation.observer import ObserverGroup, TurnObserver
from .simulation.scheduler import Scheduler
from .simulation.state import Move, SimulationState
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

    def __init__(self, name: str, view: TurnObserver) -> None:
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

    The additional options run a stage on its own through a JSON file:
    ``--parse-only`` stops after the parser and writes the World,
    ``--from-world`` reads that World instead of parsing a map, and
    ``--save-run`` writes every turn of the simulation.
    """

    def __init__(
        self,
        args: Args,
        out: TextIO | None = None,
        err: TextIO | None = None,
        make_scheduler: Callable[[Network, Pathfinder], MoveDecider] = (
            Scheduler
        ),
    ) -> None:
        """Keep the arguments, the output streams and the scheduler maker.

        Args:
            args: The parsed command-line arguments.
            out: Where the turn log goes; defaults to ``sys.stdout``.
            err: Where the terminal view, warnings and the summary go;
                defaults to ``sys.stderr``.
            make_scheduler: Builds what decides each turn's moves from the
                network and its pathfinder; defaults to ``Scheduler``. Tests
                pass another decider here instead of patching the module.
        """
        self.args = args
        self.out: TextIO = sys.stdout if out is None else out
        self.err: TextIO = sys.stderr if err is None else err
        self.make_scheduler = make_scheduler

    def run(self) -> None:
        """Parse the map, simulate it, and print the turn log.

        With ``--parse-only``, write the World and stop instead.

        Raises:
            droneflow.errors.FlyInError: On any failure: the map file
                cannot be read (``MapFileError``) or is invalid
                (``ParseError``, or ``WorldFileError`` with
                ``--from-world``), the goal is unreachable
                (``UnreachableGoalError``), the requested view cannot be
                used (``VisualizationError``), the simulation fails
                (``SimulationError``), or a JSON file cannot be written
                (``OutputFileError``).
        """
        world = self._load_world()
        if self.args.parse_only is not None:
            self._save_world(world, self.args.parse_only)
            return
        pathfinder = Pathfinder(world.network)
        engine = SimulationEngine(
            world, self.make_scheduler(world.network, pathfinder)
        )
        views = self._make_views()
        printer = TurnLogPrinter(self.out)
        recorder = None if self.args.save_run is None else RunRecorder()
        observers: list[TurnObserver] = [printer, *views]
        if recorder is not None:
            observers.append(recorder)
        # LIVE CODING (--capacity-info) 4/5: add the report here, writing
        # to self.err (stdout holds only the turn log).
        failed = True
        try:
            turns = engine.run(ObserverGroup(observers))
            failed = False
        finally:
            self._warn_close_failures(views)
            if recorder is not None:
                self._save_run(recorder, failed)
        self.err.write(
            RunSummary.from_turns(turns, world.nb_drones).describe() + "\n"
        )
        self.err.flush()

    def _load_world(self) -> World:
        """Parse the map file, or read the world file (``--from-world``).

        Raises:
            MapFileError: If the file cannot be opened or is not UTF-8
                text.
            droneflow.errors.ParseError: If the map is invalid.
            droneflow.errors.WorldFileError: If the world file is invalid.
        """
        name = self.args.map_name
        try:
            if self.args.from_world:
                return WorldFile(self.args.map_path, name).read()
            return MapParser(self.args.map_path).parse()
        except OSError as exc:
            reason = exc.strerror or type(exc).__name__
            raise MapFileError(name, reason) from exc
        except UnicodeDecodeError as exc:
            raise MapFileError(name, "not UTF-8 text") from exc

    def _save_world(self, world: World, path: str) -> None:
        """Write the World for ``--parse-only`` and say so on stderr.

        Raises:
            OutputFileError: If the file cannot be written.
        """
        WorldFile(path).write(world)
        network = world.network
        self.err.write(
            f"world: wrote {path} ({len(network.zones)} zones, "
            f"{len(network.connections)} connections, "
            f"{world.nb_drones} drones)\n"
        )
        self.err.flush()

    def _save_run(self, recorder: RunRecorder, failed: bool) -> None:
        """Write the run for ``--save-run`` and say so on stderr.

        After a failed run, the turns played so far are written, and a
        write failure is only a warning, so that it does not replace the
        error that stopped the run.

        Raises:
            OutputFileError: If the file cannot be written after a
                successful run.
        """
        path = self.args.save_run
        if path is None:
            return
        try:
            recorder.write(path)
        except OutputFileError as exc:
            if not failed:
                raise
            self.err.write(f"warning: {exc}\n")
        else:
            self.err.write(f"run: wrote {path}\n")
        self.err.flush()

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

    def _graphical_view(self) -> TurnObserver:
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
