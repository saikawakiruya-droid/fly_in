"""ZoneFlowGraph: zones and connections as a flow network, and its cut."""

from dataclasses import dataclass

from ..models.connection import Connection
from ..models.network import Network
from ..models.zone import Zone
from .flow_graph import FlowGraph


@dataclass(frozen=True)
class Bottleneck:
    """How many drones can cross the network per turn, and what limits it.

    Attributes:
        throughput: Drones that can go from the start zone to the end zone
            in one turn, capped at the limit asked for.
        zones: Zones whose ``max_drones`` is part of the cut, in
            declaration order.
        connections: Connections whose ``max_link_capacity`` is part of the
            cut, in declaration order.
    """

    throughput: int
    zones: tuple[Zone, ...]
    connections: tuple[Connection, ...]

    @property
    def limits_flow(self) -> bool:
        """Return whether a cut was found.

        False means either that the limit was reached with room to spare
        (for that many drones, nothing in the network is a bottleneck), or
        that no drone can reach the end zone at all (``throughput`` is 0).
        """
        return bool(self.zones or self.connections)


class ZoneFlowGraph:
    """Builds a ``FlowGraph`` from zones and hops, then reads its cut back.

    Every traversable zone becomes two vertices, ``in`` and ``out``,
    joined by an arc carrying the zone's ``max_drones``. A zone without
    one gets one more than the limit, so it is never saturated and never
    reported as a bottleneck. Each hop added becomes an arc from the ``out`` of
    the zone left to the ``in`` of the zone entered, carrying the
    connection's ``max_link_capacity``. The flow goes from the start
    zone's ``out`` to the end zone's ``in``, so neither of their own arcs
    is ever in the cut.

    The flow is solved once: build a new graph to solve again.
    """

    def __init__(self, network: Network, limit: int) -> None:
        """Add the vertices and the arc of every traversable zone.

        Raises:
            ValueError: If ``limit`` is less than 1.
        """
        if limit < 1:
            raise ValueError(f"limit must be at least 1: {limit}")
        self.network = network
        self.limit = limit
        self._graph = FlowGraph()
        self._ends: dict[str, tuple[int, int]] = {}
        self._zone_arcs: dict[int, Zone] = {}
        self._hop_arcs: dict[int, Connection] = {}
        for zone in network.zones.values():
            if not zone.zone_type.is_traversable:
                continue
            entry = self._graph.add_vertex()
            exit_ = self._graph.add_vertex()
            self._ends[zone.name] = (entry, exit_)
            capacity = (
                limit + 1 if zone.max_drones is None else zone.max_drones
            )
            arc = self._graph.add_arc(entry, exit_, capacity)
            self._zone_arcs[arc] = zone

    def add_hop(
        self, connection: Connection, from_zone: str, to_zone: str
    ) -> None:
        """Let drones move along ``connection`` from one zone to the other.

        Hops touching a BLOCKED zone and self-loops are ignored: they never
        carry a drone toward the end zone.

        Raises:
            ZoneNotFoundError: If either zone does not exist.
        """
        self.network.get_zone(from_zone)
        self.network.get_zone(to_zone)
        if from_zone == to_zone:
            return
        if from_zone not in self._ends or to_zone not in self._ends:
            return
        arc = self._graph.add_arc(
            self._ends[from_zone][1],
            self._ends[to_zone][0],
            connection.max_link_capacity,
        )
        self._hop_arcs[arc] = connection

    def solve(self) -> Bottleneck:
        """Return the flow and the minimum cut closest to the start zone.

        Raises:
            SimulationError: If the network has no single start or end zone
                (never the case for a parsed map).
        """
        start = self.network.start_zone.name
        end = self.network.end_zone.name
        if start not in self._ends or end not in self._ends:
            return Bottleneck(0, (), ())
        source = self._ends[start][1]
        sink = self._ends[end][0]
        flow = self._graph.max_flow(source, sink, self.limit)
        reached = self._graph.reachable_from(source)
        if sink in reached:
            return Bottleneck(flow, (), ())
        zones = [
            zone for arc, zone in self._zone_arcs.items()
            if self._crosses(arc, reached)
        ]
        cut = {
            id(connection) for arc, connection in self._hop_arcs.items()
            if self._crosses(arc, reached)
        }
        connections = tuple(
            connection for connection in self.network.connections
            if id(connection) in cut
        )
        return Bottleneck(flow, tuple(zones), connections)

    def _crosses(self, arc: int, reached: set[int]) -> bool:
        tail, head = self._graph.endpoints(arc)
        return tail in reached and head not in reached
