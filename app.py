"""Command-line arguments and the Application that runs one map.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* Args, parse_args: the command-line arguments.
* Application: orchestrates parsing, pathfinding, simulation, and output.
"""

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from engine import (
    Move,
    MoveDecider,
    ObserverGroup,
    SimulationEngine,
    TurnObserver,
)
from errors import MapFileError, VisualizationError
from map_parser import MapParser
from pathfinder import Pathfinder
from scheduler import Scheduler
from terminal_view import TerminalVisualizer
from turn_log_printer import RunSummary, TurnLogPrinter
from world import Network, World


# --- Args -------------------------------------------------------------

@dataclass(frozen=True)
class Args:
    """Parsed command-line arguments.

    Attributes:
        map_path: Path to the map file to simulate.
        terminal_view: Also show the run in the terminal (on stderr).
        matplotlib_window: Also show the run in a matplotlib window.
        map_arg: The map path exactly as typed, for messages; None means
            ``str(map_path)``. Not compared, so Args built by hand equal
            parsed ones.
    """

    map_path: Path
    terminal_view: bool = False
    matplotlib_window: bool = False
    map_arg: str | None = field(default=None, compare=False)

    @property
    def map_name(self) -> str:
        """Return the map path as the user typed it, for messages."""
        return str(self.map_path) if self.map_arg is None else self.map_arg


def parse_args(argv: list[str] | None = None) -> Args:
    """Parse command-line arguments into an Args instance.

    Args:
        argv: Argument list to parse, or None to use sys.argv.

    Returns:
        The parsed Args.

    Raises:
        SystemExit: On invalid arguments or ``--help`` (argparse prints
            the usage and exits with status 2, or 0 for help).
    """
    parser = argparse.ArgumentParser(prog="fly_in.py")
    parser.add_argument("map_path", metavar="MAP", help="map file")
    parser.add_argument(
        "--terminal-view", action="store_true",
        help="also show the run in the terminal, on stderr",
    )
    parser.add_argument(
        "--matplotlib-window", action="store_true",
        help="also show the run in a window (needs matplotlib)",
    )
    namespace = parser.parse_args(argv)
    return Args(
        map_path=Path(namespace.map_path),
        terminal_view=namespace.terminal_view,
        matplotlib_window=namespace.matplotlib_window,
        map_arg=namespace.map_path,
    )


# --- Application ------------------------------------------------------

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
