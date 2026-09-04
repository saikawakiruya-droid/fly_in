"""GraphicalVisualizer: optional graphical rendering of the simulation."""

from ..simulation.state import SimulationState


class GraphicalVisualizer:
    """Renders the network and drone positions in a graphical window."""

    def render(self, state: SimulationState) -> None:
        """Draw the current state in a graphical window."""
        raise NotImplementedError
