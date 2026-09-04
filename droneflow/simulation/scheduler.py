"""Scheduler: decides, each turn, which drone moves where."""

from ..models.network import Network
from ..pathfinding.pathfinder import Pathfinder
from .state import Move, SimulationState


class Scheduler:
    """Resolves capacity conflicts and deadlocks to plan one turn at a time."""

    def __init__(self, network: Network, pathfinder: Pathfinder) -> None:
        self.network = network
        self.pathfinder = pathfinder

    def decide_moves(self, state: SimulationState) -> list[Move]:
        """Decide this turn's moves for every undelivered drone.

        Must respect zone capacity, connection capacity, restricted-zone
        transit commitments, and avoid deadlocks between waiting drones.
        """
        raise NotImplementedError
