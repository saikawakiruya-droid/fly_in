"""SimulationEngine: runs the turn loop until every drone is delivered."""

from ..models.world import World
from ..visualization.base import Visualizer
from .scheduler import Scheduler
from .state import Move, SimulationState


class SimulationEngine:
    """Drives the turn-by-turn simulation from start to full delivery."""

    def __init__(self, world: World, scheduler: Scheduler) -> None:
        self.world = world
        self.scheduler = scheduler
        self.state = SimulationState()

    def run(self, visualizer: Visualizer | None = None) -> list[list[Move]]:
        """Run the simulation to completion.

        Args:
            visualizer: Optional renderer invoked after every turn.

        Returns:
            All turns, each a list of the moves made during that turn, in
            the order they occurred.
        """
        raise NotImplementedError
