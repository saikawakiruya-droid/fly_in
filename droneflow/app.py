"""Application: orchestrates parsing, pathfinding, simulation, and output."""

import sys
from collections.abc import Callable
from typing import TextIO

from .cli import Args
from .errors import MapFileError, VisualizationError
from .models.network import Network
from .models.world import World
from .output.turn_log_printer import TurnLogPrinter
from .parsing.map_parser import MapParser
from .pathfinding.pathfinder import Pathfinder
from .simulation.engine import MoveDecider, SimulationEngine
from .simulation.observer import ObserverGroup, TurnObserver
from .simulation.scheduling.scheduler import Scheduler
from .visualization.terminal_view import TerminalVisualizer


class Application:
    """Wires together every stage of the pipeline for a single run.

    The turn log goes to ``out`` (standard output), one line per turn as
    the run goes on, and nothing else does. The terminal view goes to
    ``err`` (standard error). With ``--graphical``, a matplotlib window
    shows the run as well.
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
            err: Where the terminal view goes; defaults to
                ``sys.stderr``.
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
                (``UnreachableGoalError``), the simulation fails
                (``SimulationError``), or the graphical view cannot be
                used (``VisualizationError``).
        """
        world = self._load_world()
        pathfinder = Pathfinder(world.network)
        engine = SimulationEngine(
            world, self.make_scheduler(world.network, pathfinder)
        )
        observers: list[TurnObserver] = [
            TurnLogPrinter(self.out),
            TerminalVisualizer(stream=self.err),
        ]
        if self.args.graphical:
            observers.append(_graphical_view(world.network))
        engine.run(ObserverGroup(observers))

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


def _graphical_view(network: Network) -> TurnObserver:
    """Open the matplotlib view, imported only when it is asked for.

    Args:
        network: The network to draw.

    Returns:
        A new GraphicalVisualizer, its window open.

    Raises:
        VisualizationError: If matplotlib is not installed or cannot show
            a window.
    """
    try:
        from .visualization.graphical_view import GraphicalVisualizer
    except ImportError as exc:
        raise VisualizationError(
            f"--graphical needs matplotlib ({exc})"
        ) from exc
    return GraphicalVisualizer(network)
