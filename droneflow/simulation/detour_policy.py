"""DetourPolicy: which longer moves a drone that would wait may take."""

from collections.abc import Mapping

from ..pathfinding.pathfinder import Hop, Pathfinder
from .evictor import Position


class DetourPolicy:
    """Lets a drone that cannot take a shortest hop go the long way round.

    A detour is one of ``Pathfinder.detour_hops``: it always lowers the
    distance to the end zone (no flowing back), but the route through it
    is longer. It is allowed when it costs no more than waiting would:

        turn_cost(v) + distance(v) <= distance(u) + ahead(u)

    where ``ahead(u)`` counts the drones that went out ahead: drones not
    yet delivered, standing in (or landing in) a zone that a shortest hop
    from ``u`` leads to, directly or further down. Each of them is a drone
    the shortest route has to let through first.
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

    def detours(self, zone_name: str) -> list[Hop]:
        """Return the zone's detour hops, cheapest first."""
        return [hop for _, hop in self._detours.get(zone_name, [])]

    def allowed(
        self, zone_name: str, positions: Mapping[int, Position]
    ) -> list[Hop]:
        """Return the detours a drone in this zone may take now.

        Args:
            zone_name: Where the drone stands.
            positions: Where every drone on the map will be after the moves
                decided so far this turn (the scheduler's positions).

        Returns:
            The allowed detours, cheapest first; empty if the zone cannot
            reach the end zone.
        """
        here = self.pathfinder.distance(zone_name)
        if here is None:
            return []
        below = self._below.get(zone_name, set())
        ahead = sum(1 for zone, _ in positions.values() if zone in below)
        budget = here + ahead
        return [
            hop for total, hop in self._detours.get(zone_name, [])
            if total <= budget
        ]

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
