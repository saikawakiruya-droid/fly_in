"""Pathfinder: next hops toward the end zone, shortest and detours."""

from dataclasses import dataclass

from ..errors import UnreachableGoalError
from ..models.connection import Connection
from ..models.network import Network
from ..models.zone import Zone, ZoneType
from .distance_map import DistanceMap


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

        Raises:
            UnreachableGoalError: If the end zone cannot be reached from the
                start zone.
        """
        self.network = network
        self._distances = DistanceMap(network)
        start = network.start_zone
        if self._distances.distance(start.name) is None:
            raise UnreachableGoalError(start.name, network.end_zone.name)

    def distance(self, zone_name: str) -> int | None:
        """Return the turns needed to reach the end zone from this zone.

        Returns:
            The shortest turn count, or None if the end zone is unreachable
            from this zone.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        return self._distances.distance(zone_name)

    def next_hops(self, zone_name: str) -> list[Hop]:
        """Return every move that keeps a drone on a shortest route.

        A neighbor qualifies when entering it and then following its own
        shortest route costs exactly this zone's distance. Priority zones
        come first among these equally short hops; a longer priority detour
        is never included. Otherwise the order follows connection
        declaration order.

        Returns:
            The qualifying hops, or an empty list if this zone is the end
            zone or cannot reach it.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        here = self._distances.distance(zone_name)
        if here is None or here == 0:
            return []
        hops: list[Hop] = []
        seen: set[str] = set()
        for connection in self.network.neighbors(zone_name):
            zone = self.network.get_zone(connection.other_end(zone_name))
            there = self._distances.distance(zone.name)
            if there is None or zone.name in seen:
                continue
            # A zone with a distance is traversable, so turn_cost is safe.
            if zone.zone_type.turn_cost + there == here:
                seen.add(zone.name)
                hops.append(Hop(connection, zone))
        hops.sort(key=lambda hop: hop.zone.zone_type is not ZoneType.PRIORITY)
        return hops

    def detour_hops(self, zone_name: str) -> list[Hop]:
        """Return every move off the shortest routes that can still finish.

        A neighbor qualifies when the end zone can be reached from it and
        entering it is not one of ``next_hops``: entering it and then
        following its shortest route costs more than this zone's distance.
        It may be closer to the end zone, as far, or farther; whether a
        drone may take it is up to the caller. Self-loops are left out.
        The hops are ordered by that total cost, then by connection
        declaration order.

        Returns:
            The qualifying hops, or an empty list if this zone is the end
            zone or cannot reach it.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        here = self._distances.distance(zone_name)
        if here is None or here == 0:
            return []
        costed: list[tuple[int, Hop]] = []
        seen: set[str] = set()
        for connection in self.network.neighbors(zone_name):
            zone = self.network.get_zone(connection.other_end(zone_name))
            there = self._distances.distance(zone.name)
            if there is None or zone.name == zone_name or zone.name in seen:
                continue
            # A zone with a distance is traversable, so turn_cost is safe.
            total = zone.zone_type.turn_cost + there
            if total > here:
                seen.add(zone.name)
                costed.append((total, Hop(connection, zone)))
        costed.sort(key=lambda item: item[0])
        return [hop for _, hop in costed]
