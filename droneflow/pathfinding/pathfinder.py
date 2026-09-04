"""Pathfinder: hand-rolled weighted search respecting zone-type costs."""

from dataclasses import dataclass

from ..models.network import Network


@dataclass
class Route:
    """A concrete route through the network.

    Attributes:
        zones: Ordered zone names from start to end, inclusive.
        total_cost: Sum of movement costs along the path.
    """

    zones: list[str]
    total_cost: int


class Pathfinder:
    """Computes movement-cost-aware paths without networkx/graphlib."""

    def __init__(self, network: Network) -> None:
        self.network = network

    def find_path(self, start: str, end: str) -> Route:
        """Find a single lowest-cost path from start to end.

        Zone-type movement costs apply (normal/priority = 1, restricted = 2,
        blocked = never traversable), and priority zones should be preferred
        on ties.
        """
        raise NotImplementedError

    def find_k_paths(self, start: str, end: str, k: int) -> list[Route]:
        """Find up to k candidate paths, for load-balancing across drones."""
        raise NotImplementedError
