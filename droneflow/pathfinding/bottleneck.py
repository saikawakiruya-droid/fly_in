"""Bottleneck finders: over every connection, or over shortest hops only."""

from ..models.network import Network
from .pathfinder import Pathfinder
from .zone_flow import Bottleneck, ZoneFlowGraph


class ConnectionBottleneck:
    """Finds the bottleneck when drones may use every connection.

    Each connection can be crossed both ways, so it becomes one hop in
    each direction; the flow can cancel itself across the two, so the
    maximum flow is that of an undirected link.
    """

    def __init__(self, network: Network) -> None:
        """Keep the network to analyse."""
        self.network = network

    def find(self, limit: int) -> Bottleneck:
        """Return the per-turn throughput, capped at ``limit``, and its cut.

        Raises:
            ValueError: If ``limit`` is less than 1.
        """
        graph = ZoneFlowGraph(self.network, limit)
        for connection in self.network.connections:
            graph.add_hop(connection, connection.zone_a, connection.zone_b)
            graph.add_hop(connection, connection.zone_b, connection.zone_a)
        return graph.solve()


class ShortestHopBottleneck:
    """Finds the bottleneck when drones only take shortest next hops.

    Only the moves ``Pathfinder.next_hops`` offers are used, in the
    direction it offers them. Comparing with ``ConnectionBottleneck``
    shows how much throughput keeping to shortest routes gives up.
    """

    def __init__(self, network: Network, pathfinder: Pathfinder) -> None:
        """Keep the network and the pathfinder that gives its hops."""
        self.network = network
        self.pathfinder = pathfinder

    def find(self, limit: int) -> Bottleneck:
        """Return the per-turn throughput, capped at ``limit``, and its cut.

        Raises:
            ValueError: If ``limit`` is less than 1.
        """
        graph = ZoneFlowGraph(self.network, limit)
        for name in self.network.zones:
            for hop in self.pathfinder.next_hops(name):
                graph.add_hop(hop.connection, name, hop.zone.name)
        return graph.solve()
