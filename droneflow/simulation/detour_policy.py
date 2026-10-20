"""DetourPolicy: which longer moves a drone that would wait may take."""

from collections.abc import Mapping

from ..pathfinding.pathfinder import Hop, Pathfinder
from .evictor import Position


class DetourPolicy:
    """Lets a drone that cannot take a shortest hop go the long way round.

    A detour is one of ``Pathfinder.detour_hops`` from the drone's zone
    ``u`` into a zone ``v``. It may lead sideways or away from the end
    zone, but never into a zone the drone has already been in: that is
    what keeps drones from flowing back and forth. It is allowed when it
    is expected to be no slower than queuing on the shortest route:

        turn_cost(v) + distance(v) + queue(v) <= distance(u) + ahead(u)

    ``ahead(u)`` counts the drones in the zones that a shortest hop from
    ``u`` leads to, directly or further down: the drones the shortest
    route has to let through first. ``queue(v)`` counts the same for
    ``v``, plus the drones in ``v`` itself. Drones are counted where they
    will be after the moves decided so far this turn (landing targets for
    drones in flight).

    The policy remembers every zone each drone has been in, from the
    positions the scheduler reports at the start of each turn.
    """

    def __init__(
        self, pathfinder: Pathfinder, hops: Mapping[str, list[Hop]]
    ) -> None:
        """Cache every zone's detours and the zones below it.

        Args:
            pathfinder: Answers distances and detour hops.
            hops: The shortest next hops of every zone.
        """
        self.pathfinder = pathfinder
        self._detours: dict[str, list[tuple[int, Hop]]] = {
            name: self._costed(pathfinder, name) for name in hops
        }
        self._below: dict[str, set[str]] = {
            name: self._zones_below(name, hops) for name in hops
        }
        self._visited: dict[int, set[str]] = {}

    def detours(self, zone_name: str) -> list[Hop]:
        """Return the zone's detour hops, cheapest first.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        self.pathfinder.network.get_zone(zone_name)
        return [hop for _, hop in self._detours.get(zone_name, [])]

    def remember(self, positions: Mapping[int, Position]) -> None:
        """Record the zone every drone is in (or landing in) as visited."""
        for drone_id, (zone_name, _) in positions.items():
            self._visited.setdefault(drone_id, set()).add(zone_name)

    def forget(self) -> None:
        """Drop every visited zone, for a new simulation."""
        self._visited.clear()

    def allowed(
        self,
        drone_id: int,
        zone_name: str,
        positions: Mapping[int, Position],
    ) -> list[Hop]:
        """Return the detours this drone may take now, cheapest first.

        Args:
            drone_id: The drone deciding.
            zone_name: Where the drone stands.
            positions: Where every drone on the map will be after the moves
                decided so far this turn (the scheduler's positions).

        Returns:
            The allowed detours; empty if the zone cannot reach the end
            zone.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        here = self.pathfinder.distance(zone_name)
        if here is None:
            return []
        budget = here + self._count(self._below[zone_name], positions)
        visited = self._visited.get(drone_id, set())
        allowed: list[Hop] = []
        for total, hop in self._detours[zone_name]:
            target = hop.zone.name
            if target in visited:
                continue
            queue = self._count(self._below[target] | {target}, positions)
            if total + queue <= budget:
                allowed.append(hop)
        return allowed

    @staticmethod
    def _count(zones: set[str], positions: Mapping[int, Position]) -> int:
        return sum(1 for zone, _ in positions.values() if zone in zones)

    @staticmethod
    def _costed(pathfinder: Pathfinder, name: str) -> list[tuple[int, Hop]]:
        """Return the zone's detours with their total cost to the end."""
        costed: list[tuple[int, Hop]] = []
        for hop in pathfinder.detour_hops(name):
            there = pathfinder.distance(hop.zone.name)
            if there is not None:  # always true for a detour
                costed.append((hop.zone.zone_type.turn_cost + there, hop))
        return costed

    @staticmethod
    def _zones_below(name: str, hops: Mapping[str, list[Hop]]) -> set[str]:
        """Return the zones reachable from ``name`` by shortest hops."""
        below: set[str] = set()
        stack = [name]
        while stack:
            for hop in hops.get(stack.pop(), []):
                if hop.zone.name not in below:
                    below.add(hop.zone.name)
                    stack.append(hop.zone.name)
        return below
