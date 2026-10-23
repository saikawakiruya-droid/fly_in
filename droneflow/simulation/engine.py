"""SimulationEngine: runs the turn loop until every drone is delivered."""

from typing import Protocol

from ..errors import SimulationError
from ..models.world import World
from .observer import TurnObserver
from .state import Move, MoveOrder, SimulationState
from .turn_resolver import TurnResolver


class MoveDecider(Protocol):
    """Anything that decides each turn's moves (the ``Scheduler``)."""

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Return the orders for the turn after ``state``.

        Args:
            state: The current state.

        Returns:
            The orders for drones standing in zones.
        """
        ...


def default_turn_limit(world: World) -> int:
    """Return a turn count no sensible schedule should ever exceed.

    It is a safety limit to catch a scheduler that loops forever, not a
    bound proved for every schedule: sending the drones one at a time is
    always possible and needs about two turns per zone per drone, so
    ``2 * zones * nb_drones`` turns is far more than any real run takes.

    Args:
        world: The parsed map and drone count.

    Returns:
        ``2 * zones * nb_drones`` (at least one zone is counted).
    """
    return 2 * max(len(world.network.zones), 1) * world.nb_drones


class SimulationEngine:
    """Drives the turn-by-turn simulation from start to full delivery.

    Composes the state, the rules (``TurnResolver``) and the decisions
    (any ``MoveDecider``, normally the ``Scheduler``): each turn the
    decider orders moves, the resolver checks and applies them, and the
    resulting moves are recorded.
    """

    def __init__(
        self,
        world: World,
        decider: MoveDecider,
        max_turns: int | None = None,
    ) -> None:
        """Set up all drones in the start zone.

        Args:
            world: The parsed map and drone count.
            decider: Decides each turn's moves (normally a ``Scheduler``).
            max_turns: Safety limit on the number of turns; defaults to
                ``default_turn_limit(world)``.
        """
        self.world = world
        self.decider = decider
        self.state = SimulationState(world.network, world.nb_drones)
        self.resolver = TurnResolver(world.network)
        self.max_turns = (
            default_turn_limit(world) if max_turns is None else max_turns
        )

    def run(
        self, observer: TurnObserver | None = None
    ) -> list[list[Move]]:
        """Run the simulation to completion.

        Args:
            observer: Optional observer: ``begin`` is called before the
                first turn, ``render(state, moves)`` after every applied
                turn, and ``close`` once at the end, even on error
                (including an error raised by ``begin``).

        Returns:
            All turns, each a list of the moves made during that turn, in
            drone_id order. No turn is empty.

        Raises:
            SimulationError: If the scheduler orders an illegal move, if a
                drone in flight cannot land (stuck on its connection), if a
                turn passes with no drone moving (the state would never
                change again), or if ``max_turns`` is exceeded.
        """
        turns: list[list[Move]] = []
        try:
            if observer is not None:
                observer.begin(self.state)
            while not self.state.is_complete:
                turns.append(self._play_turn())
                if observer is not None:
                    observer.render(self.state, turns[-1])
        finally:
            if observer is not None:
                observer.close()
        return turns

    def _play_turn(self) -> list[Move]:
        """Order, check and apply one turn; return its moves.

        Returns:
            The turn's moves, in drone_id order (never empty).

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
        orders = self.decider.decide_moves(self.state)
        moves = self.resolver.resolve(self.state, orders)
        if not moves:
            raise SimulationError(
                f"turn {self.state.turn_number}: no drone moved, "
                "so the simulation cannot progress"
            )
        return moves
