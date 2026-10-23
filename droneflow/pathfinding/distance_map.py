"""DistanceMap: turns needed to reach the end zone, from every zone."""

import heapq

from ..models.network import Network


class DistanceMap:
    """Precomputed shortest turn counts from each zone to the end zone.

    Built once with a single Dijkstra search started from the end zone over
    the hand-built ``Network`` adjacency (no graph libraries). Moving from a
    zone into a neighbor costs the neighbor's ``zone_type.turn_cost``, so the
    search walks the connections backwards: reaching zone ``u`` from its
    neighbor ``w`` adds ``u``'s turn cost to ``w``'s distance.

    BLOCKED zones are never entered nor passed through, so they never get a
    distance. Zone and connection capacities are deliberately ignored; they
    change every turn and are the scheduler's concern.
    """

    def __init__(self, network: Network) -> None:
        """Run the search once over the network.

        Args:
            network: The network to measure.
        """
        self.network = network
        self._distances = self._compute()

    def distance(self, zone_name: str) -> int | None:
        """Return the turns needed to go from this zone to the end zone.

        Args:
            zone_name: The zone to start from.

        Returns:
            The shortest turn count, 0 for the end zone itself, or None if
            the end zone cannot be reached from this zone (always the case
            for BLOCKED zones).

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        self.network.get_zone(zone_name)
        return self._distances.get(zone_name)

    def _compute(self) -> dict[str, int]:
        """Run Dijkstra from the end zone and return every distance found.

        Returns:
            The distance of every zone that can reach the end zone; empty
            if the end zone itself cannot be entered.
        """
        end = self.network.end_zone
        if not end.zone_type.is_traversable:
            return {}
        distances: dict[str, int] = {end.name: 0}
        heap: list[tuple[int, str]] = [(0, end.name)]
        while heap:
            dist, name = heapq.heappop(heap)
            if dist > distances[name]:
                continue
            # Only traversable zones are ever pushed, so turn_cost is safe.
            step = self.network.get_zone(name).zone_type.turn_cost
            for connection in self.network.neighbors(name):
                previous = self.network.get_zone(connection.other_end(name))
                if not previous.zone_type.is_traversable:
                    continue
                candidate = dist + step
                known = distances.get(previous.name)
                if known is None or candidate < known:
                    distances[previous.name] = candidate
                    heapq.heappush(heap, (candidate, previous.name))
        return distances
