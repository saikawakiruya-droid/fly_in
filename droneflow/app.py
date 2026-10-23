"""Application: orchestrates parsing, pathfinding, simulation, and output."""

import sys
from collections.abc import Callable
from typing import TextIO

from .cli import Args
from .errors import MapFileError
from .models.network import Network
from .models.world import World
from .output.summary import RunSummary
from .output.turn_log_printer import TurnLogPrinter
from .parsing.map_parser import MapParser
from .pathfinding.pathfinder import Pathfinder
from .simulation.engine import MoveDecider, SimulationEngine
from .simulation.observer import ObserverGroup, TurnObserver
from .simulation.scheduling.scheduler import Scheduler
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
        """Wrap a view.

        Args:
            name: Short name of the view, used in warnings.
            view: The view to forward to.
        """
        self.name = name
        self.view = view
        self.error: Exception | None = None

    def begin(self, state: SimulationState) -> None:
        """Forward to the view.

        Args:
            state: The state before the first turn.
        """
        self.view.begin(state)

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Forward to the view.

        Args:
            state: The state after the turn.
            moves: The moves made during the turn.
        """
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
                network and its pathfinder; defaults to ``Scheduler``. Any
                other ``MoveDecider`` can be plugged in here.
        """
        self.args = args
        self.out: TextIO = sys.stdout if out is None else out
        self.err: TextIO = sys.stderr if err is None else err
        self.make_scheduler = make_scheduler

    def run(self) -> None:
        """Parse the map, simulate it, and print the turn log.

        Raises:
            droneflow.errors.FlyInError: On any failure: the map file
                cannot be read (``MapFileError``) or is invalid
                (``ParseError``), the goal is unreachable
                (``UnreachableGoalError``), or the simulation fails
                (``SimulationError``).
        """
        world = self._load_world()
        pathfinder = Pathfinder(world.network)
        engine = SimulationEngine(
            world, self.make_scheduler(world.network, pathfinder)
        )
        views = self._make_views()
        printer = TurnLogPrinter(self.out)
        observers: list[TurnObserver] = [printer, *views]
        try:
            turns = engine.run(ObserverGroup(observers))
        finally:
            self._warn_close_failures(views)
        self.err.write(
            RunSummary.from_turns(turns, world.nb_drones).describe() + "\n"
        )
        self.err.flush()

    def _load_world(self) -> World:
        """Parse the map file.

        Returns:
            The World to simulate.

        Raises:
            MapFileError: If the file cannot be opened or is not UTF-8
                text.
            droneflow.errors.ParseError: If the map is invalid.
        """
        name = self.args.map_name
        try:
            return MapParser(self.args.map_path).parse()
        except OSError as exc:
            reason = exc.strerror or type(exc).__name__
            raise MapFileError(name, reason) from exc
        except UnicodeDecodeError as exc:
            raise MapFileError(name, "not UTF-8 text") from exc

    def _make_views(self) -> list[_GuardedView]:
        """Build the views selected by --visual and --step.

        Returns:
            The views, each wrapped so that a failing close is kept.
        """
        views: list[_GuardedView] = []
        if self.args.visual == "terminal":
            views.append(_GuardedView(
                "terminal",
                TerminalVisualizer(stream=self.err, step=self.args.step),
            ))
        return views

    def _warn_close_failures(self, views: list[_GuardedView]) -> None:
        """Write one warning line per view whose ``close`` failed.

        Args:
            views: The views, after they were closed.
        """
        for view in views:
            if view.error is not None:
                self.err.write(
                    f"warning: could not close the {view.name} view: "
                    f"{view.error}\n"
                )
        self.err.flush()
