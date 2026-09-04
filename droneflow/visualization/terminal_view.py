"""TerminalVisualizer: colored terminal rendering of the simulation."""

from ..simulation.state import SimulationState


class TerminalVisualizer:
    """Renders zone occupancy and drone positions as colored terminal text."""

    def render(self, state: SimulationState) -> None:
        """Print the current state to the terminal, using each zone's color."""
        raise NotImplementedError
