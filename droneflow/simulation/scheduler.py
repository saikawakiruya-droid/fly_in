"""Scheduler: decides, each turn, which drone moves where."""

from ..models.network import Network
from ..pathfinding.pathfinder import Pathfinder
from .state import MoveOrder, SimulationState


class Scheduler:
    """Resolves capacity conflicts and deadlocks to plan one turn at a time."""

    def __init__(self, network: Network, pathfinder: Pathfinder) -> None:
        self.network = network
        self.pathfinder = pathfinder

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Decide this turn's moves for the drones standing in zones.

        Returns at most one order per drone; drones without an order wait.
        Drones in flight toward a restricted zone must not get an order:
        the engine lands them automatically, and their reservations and
        connection use are already visible through ``state``.

        Must respect zone capacity, connection capacity, restricted-zone
        transit commitments, and avoid deadlocks between waiting drones.
        The engine rejects any illegal order with ``SimulationError``.
        """
        raise NotImplementedError
