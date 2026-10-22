"""TurnObserver: what the engine calls each turn, and a group of them."""

from collections.abc import Sequence
from typing import Protocol

from .state import Move, SimulationState


class TurnObserver(Protocol):
    """Anything that follows the simulation as it runs.

    ``SimulationEngine.run`` calls ``begin`` once before the first turn,
    ``render`` after every applied turn, and ``close`` once at the end,
    even when the run stops with an error. Observers only read the state.
    The turn log printer and every view are observers.
    """

    def begin(self, state: SimulationState) -> None:
        """Take the initial state (turn 0, every drone in the start zone)."""
        ...

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Take the state after a turn.

        Args:
            state: The state with the turn applied.
            moves: The moves made during that turn, in drone_id order.
        """
        ...

    def close(self) -> None:
        """Release whatever the observer holds (e.g. a window)."""
        ...


class ObserverGroup:
    """Forwards every call to each of its observers, in order.

    The application uses it to give the engine the turn log printer and
    the chosen views as a single observer.
    """

    def __init__(self, observers: Sequence[TurnObserver]) -> None:
        """Keep the observers to forward to."""
        self.observers: list[TurnObserver] = list(observers)

    def begin(self, state: SimulationState) -> None:
        """Give the initial state to every observer."""
        for observer in self.observers:
            observer.begin(state)

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Give the turn to every observer."""
        for observer in self.observers:
            observer.render(state, moves)

    def close(self) -> None:
        """Close every observer, even if closing one of them fails.

        Observers are closed in order. If several fail, the last failure is
        raised, with the earlier ones chained to it as context.
        """
        self._close_from(0)

    def _close_from(self, index: int) -> None:
        """Close observers[index:]; ``finally`` chains failures as context."""
        if index >= len(self.observers):
            return
        try:
            self.observers[index].close()
        finally:
            self._close_from(index + 1)
