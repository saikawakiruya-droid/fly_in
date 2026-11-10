"""Shortest routes to the end zone: the distances and the next hops.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* DistanceMap: turns needed to reach the end zone, from every zone.
* Pathfinder: next hops toward the end zone, shortest and detours.
"""

import heapq
from dataclasses import dataclass

from errors import UnreachableGoalError
from world import Connection, Network, Zone, ZoneType


# --- DistanceMap ------------------------------------------------------

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


# --- Pathfinder -------------------------------------------------------

@dataclass(frozen=True)
class Hop:
    """One possible move: the connection to take and the zone it leads to.

    Attributes:
        connection: The connection the drone would traverse.
        zone: The zone the drone would enter.
    """

    connection: Connection
    zone: Zone


class Pathfinder:
    """Answers "where should a drone go next" using distances to the goal.

    Distances come from a ``DistanceMap`` built once at construction time.
    Capacity is not considered here; the scheduler decides whether a hop is
    actually free this turn.
    """

    def __init__(self, network: Network) -> None:
        """Precompute distances and check that the goal is reachable.

        Args:
            network: The network to route drones through.

        Raises:
            UnreachableGoalError: If the end zone cannot be reached from the
                start zone.
        """
        self.network = network
        self._distance_map = DistanceMap(network)
        start = network.start_zone
        if self._distance_map.distance(start.name) is None:
            raise UnreachableGoalError(start.name, network.end_zone.name)

    def distance(self, zone_name: str) -> int | None:
        """Return the turns needed to reach the end zone from this zone.

        Args:
            zone_name: The zone to start from.

        Returns:
            The shortest turn count, or None if the end zone is unreachable
            from this zone.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        return self._distance_map.distance(zone_name)

    def next_hops(self, zone_name: str) -> list[Hop]:
        """Return every hop that keeps a drone on a shortest route.

        A neighbor qualifies when entering it and then following its own
        shortest route costs exactly this zone's distance. Priority zones
        come first among these equally short hops; a longer priority detour
        is never included. Otherwise the order follows connection
        declaration order.

        Args:
            zone_name: The zone the drone is in.

        Returns:
            The qualifying hops, or an empty list if this zone is the end
            zone or cannot reach it.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        distance = self._distance_map.distance(zone_name)
        hops = [
            hop for total, hop in self._costed_hops(zone_name)
            if total == distance
        ]
        hops.sort(key=lambda hop: hop.zone.zone_type is not ZoneType.PRIORITY)
        return hops

    def detour_hops(self, zone_name: str) -> list[Hop]:
        """Return every hop off the shortest routes that can still finish.

        A neighbor qualifies when the end zone can be reached from it and
        entering it is not one of ``next_hops``: entering it and then
        following its shortest route costs more than this zone's distance.
        It may be closer to the end zone, as far, or farther; whether a
        drone may take it is up to the caller. Self-loops are left out.
        The hops are ordered by that total cost, then by connection
        declaration order.

        Args:
            zone_name: The zone the drone is in.

        Returns:
            The qualifying hops, or an empty list if this zone is the end
            zone or cannot reach it.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        distance = self._distance_map.distance(zone_name)
        if distance is None:
            return []
        costed = [
            (total, hop) for total, hop in self._costed_hops(zone_name)
            if total > distance
        ]
        costed.sort(key=lambda item: item[0])
        return [hop for _, hop in costed]

    def route_cost(self, hop: Hop) -> int:
        """Return the turns to the end zone when going through ``hop``.

        That is the turns to enter the hop's zone plus that zone's own
        distance.

        Args:
            hop: A hop to a neighboring zone.

        Returns:
            The total turn count to the end zone through the hop.

        Raises:
            ValueError: If the end zone cannot be reached from the hop's
                zone (never the case for ``next_hops`` and
                ``detour_hops``).
        """
        distance = self._distance_map.distance(hop.zone.name)
        if distance is None:
            raise ValueError(f"{hop.zone.name!r} cannot reach the end zone")
        return hop.zone.zone_type.turn_cost + distance

    def _costed_hops(self, zone_name: str) -> list[tuple[int, Hop]]:
        """Return every hop from the zone toward a zone that can finish.

        Each hop comes with its ``route_cost``. Self-loops are left out,
        and so is everything when this zone is the end zone or cannot
        reach it. The order is connection declaration order.

        Args:
            zone_name: The zone the drone is in.

        Returns:
            ``(route_cost, hop)`` pairs, one per neighboring zone.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        distance = self._distance_map.distance(zone_name)
        if distance is None or distance == 0:
            return []
        hops: list[tuple[int, Hop]] = []
        seen: set[str] = set()
        for connection in self.network.neighbors(zone_name):
            zone = self.network.get_zone(connection.other_end(zone_name))
            if zone.name == zone_name or zone.name in seen:
                continue
            if self._distance_map.distance(zone.name) is None:
                continue
            seen.add(zone.name)
            hop = Hop(connection, zone)
            hops.append((self.route_cost(hop), hop))
        return hops
