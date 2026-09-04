"""Visualizer: the common interface every view implements."""

from typing import Protocol

from ..simulation.state import SimulationState


class Visualizer(Protocol):
    """Anything that can render a SimulationState after a turn."""

    def render(self, state: SimulationState) -> None:
        """Render the current state."""
        ...
