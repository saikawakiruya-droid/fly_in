"""Visualizer: the common interface every view implements."""

from typing import Protocol

from ..simulation.state import Move, SimulationState


class Visualizer(Protocol):
    """Anything that can show the simulation as it runs.

    ``SimulationEngine.run`` calls ``begin`` once before the first turn,
    ``render`` after every applied turn, and ``close`` once at the end,
    even when the run stops with an error. Views only read the state.
    """

    def begin(self, state: SimulationState) -> None:
        """Show the initial state (turn 0, every drone in the start zone)."""
        ...

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Show the state after a turn.

        Args:
            state: The state with the turn applied.
            moves: The moves made during that turn, in drone_id order.
        """
        ...

    def close(self) -> None:
        """Release whatever the view holds (e.g. a window)."""
        ...
