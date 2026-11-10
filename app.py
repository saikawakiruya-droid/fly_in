"""Application: orchestrates parsing, pathfinding, simulation, and output."""

import sys
from collections.abc import Callable
from typing import TextIO

from cli import Args
from engine import MoveDecider, SimulationEngine
from engine_state import Move
from errors import MapFileError, VisualizationError
from map_parser import MapParser
from pathfinder import Pathfinder
from run_summary import RunSummary
from scheduler import Scheduler
from terminal_view import TerminalVisualizer
from turn_log_printer import TurnLogPrinter
from turn_observer import ObserverGroup, TurnObserver
from world import World
from world_network import Network


class Application:
    """Wires together every stage of the pipeline for a single run.

    The turn log goes to ``stdout`` (standard output), one line per turn as
    the run goes on, and nothing else does. The final summary goes to
    ``stderr`` (standard error). Each view is used only when its option is
    given: ``--terminal-view`` draws the run on ``stderr``, and
    ``--matplotlib-window`` shows it in a matplotlib window.
    """

    def __init__(
        self,
        args: Args,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
        make_scheduler: Callable[[Network, Pathfinder], MoveDecider] = (
            Scheduler
        ),
    ) -> None:
        """Keep the arguments, the output streams and the scheduler maker.

        Args:
            args: The parsed command-line arguments.
            stdout: Where the turn log goes; defaults to ``sys.stdout``.
            stderr: Where the terminal view and the summary go; defaults to
                ``sys.stderr``.
            make_scheduler: Builds what decides each turn's moves from the
                network and its pathfinder; defaults to ``Scheduler``. Any
                other ``MoveDecider`` can be plugged in here.
        """
        self.args = args
        self.stdout: TextIO = sys.stdout if stdout is None else stdout
        self.stderr: TextIO = sys.stderr if stderr is None else stderr
        self.make_scheduler = make_scheduler

    def run(self) -> None:
        """Parse the map, simulate it, and print the turn log.

        Raises:
            errors.FlyInError: On any failure: the map file
                cannot be read (``MapFileError``) or is invalid
                (``ParseError``), the goal is unreachable
                (``UnreachableGoalError``), the simulation fails
                (``SimulationError``), or the matplotlib window cannot be
                used (``VisualizationError``).
        """
        world = self._load_world()
        pathfinder = Pathfinder(world.network)
        engine = SimulationEngine(
            world, self.make_scheduler(world.network, pathfinder)
        )
        turns = engine.run(self._observers(world.network))
        self._print_summary(turns, world.nb_drones)

    def _load_world(self) -> World:
        """Parse the map file.

        Returns:
            The World to simulate.

        Raises:
            MapFileError: If the file cannot be opened or is not UTF-8
                text.
            errors.ParseError: If the map is invalid.
        """
        name = self.args.map_name
        try:
            return MapParser(self.args.map_path).parse()
        except OSError as exc:
            reason = exc.strerror or type(exc).__name__
            raise MapFileError(name, reason) from exc
        except UnicodeDecodeError as exc:
            raise MapFileError(name, "not UTF-8 text") from exc

    def _observers(self, network: Network) -> ObserverGroup:
        """Gather what watches the run: the turn log and the views.

        Args:
            network: The network to draw in the matplotlib window.

        Returns:
            The turn log printer, then the terminal view if
            ``--terminal-view`` was given, then the matplotlib window if
            ``--matplotlib-window`` was given.

        Raises:
            VisualizationError: If the matplotlib window cannot be used.
        """
        observers: list[TurnObserver] = [TurnLogPrinter(self.stdout)]
        if self.args.terminal_view:
            observers.append(TerminalVisualizer(stream=self.stderr))
        if self.args.matplotlib_window:
            observers.append(_matplotlib_window(network))
        return ObserverGroup(observers)

    def _print_summary(self, turns: list[list[Move]], nb_drones: int) -> None:
        """Write the run's summary to ``stderr``.

        Args:
            turns: The moves of every turn.
            nb_drones: How many drones the map has.
        """
        self.stderr.write(
            RunSummary.from_turns(turns, nb_drones).describe() + "\n"
        )
        self.stderr.flush()


def _matplotlib_window(network: Network) -> TurnObserver:
    """Open the matplotlib view, imported only when it is asked for.

    Args:
        network: The network to draw.

    Returns:
        A new MatplotlibWindowVisualizer, its window open.

    Raises:
        VisualizationError: If matplotlib is not installed or cannot show
            a window.
    """
    try:
        from matplotlib_window import MatplotlibWindowVisualizer
    except ImportError as exc:
        raise VisualizationError(
            f"--matplotlib-window needs matplotlib ({exc})"
        ) from exc
    return MatplotlibWindowVisualizer(network)
