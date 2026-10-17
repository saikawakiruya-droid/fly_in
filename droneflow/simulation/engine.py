"""SimulationEngine: runs the turn loop until every drone is delivered."""

from ..errors import SimulationError
from ..models.world import World
from ..visualization.base import Visualizer
from .scheduler import Scheduler
from .state import Move, SimulationState
from .turn_resolver import TurnResolver


def default_turn_limit(world: World) -> int:
    """Return a turn count no sensible schedule should ever exceed.

    Sending the drones one at a time is always possible, and one drone
    needs at most two turns per zone on a simple path. So
    ``2 * zones * nb_drones`` turns is generous for any real scheduler and
    only catches one that loops forever.
    """
    return 2 * max(len(world.network.zones), 1) * world.nb_drones


class SimulationEngine:
    """Drives the turn-by-turn simulation from start to full delivery.

    Composes the state, the rules (``TurnResolver``) and the decisions
    (``Scheduler``): each turn the scheduler orders moves, the resolver
    checks and applies them, and the resulting moves are recorded.
    """

    def __init__(
        self,
        world: World,
        scheduler: Scheduler,
        max_turns: int | None = None,
    ) -> None:
        """Set up all drones in the start zone.

        Args:
            world: The parsed map and drone count.
            scheduler: Decides each turn's moves.
            max_turns: Safety limit on the number of turns; defaults to
                ``default_turn_limit(world)``.
        """
        self.world = world
        self.scheduler = scheduler
        self.state = SimulationState(world.network, world.nb_drones)
        self.resolver = TurnResolver(world.network)
        self.max_turns = (
            default_turn_limit(world) if max_turns is None else max_turns
        )

    def run(self, visualizer: Visualizer | None = None) -> list[list[Move]]:
        """Run the simulation to completion.

        Args:
            visualizer: Optional view: ``begin`` is called before the
                first turn, ``render(state, moves)`` after every applied
                turn, and ``close`` once at the end, even on error.

        Returns:
            All turns, each a list of the moves made during that turn, in
            drone_id order. No turn is empty.

        Raises:
            SimulationError: If the scheduler orders an illegal move, if a
                turn passes with no drone moving (the state would never
                change again), or if ``max_turns`` is exceeded.
        """
        turns: list[list[Move]] = []
        if visualizer is not None:
            visualizer.begin(self.state)
        try:
            while not self.state.is_complete:
                turns.append(self._play_turn())
                if visualizer is not None:
                    visualizer.render(self.state, turns[-1])
        finally:
            if visualizer is not None:
                visualizer.close()
        return turns

    def _play_turn(self) -> list[Move]:
        """Order, check and apply one turn; return its moves.

        Raises:
            SimulationError: On an illegal order, a turn where nothing
                moves, or when ``max_turns`` is reached.
        """
        if self.state.turn_number >= self.max_turns:
            raise SimulationError(
                f"not finished after {self.max_turns} turns "
                f"({self.state.delivered_count}/{self.world.nb_drones} "
                "drones delivered)"
            )
        orders = self.scheduler.decide_moves(self.state)
        moves = self.resolver.resolve(self.state, orders)
        if not moves:
            raise SimulationError(
                f"turn {self.state.turn_number}: no drone moved, "
                "so the simulation cannot progress"
            )
        return moves
