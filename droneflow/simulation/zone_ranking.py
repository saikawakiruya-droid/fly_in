"""ZoneRanking: the order in which the scheduler decides the zones."""

from collections.abc import Mapping

from ..models.network import Network
from ..models.zone import ZoneType
from ..pathfinding.pathfinder import Hop, Pathfinder
from .detour_policy import DetourPolicy


class ZoneRanking:
    """Numbers the zones that can reach the end zone in decision order.

    Closest to the end zone first, so drones leaving a zone free its room
    before the drones behind them ask for it. Among zones at the same
    distance: zones on the priority route first, then zones with fewer
    exits (shortest hops and detours), so a drone with a choice does not
    take the only way out of another; then declaration order. The ranks
    are computed once.
    """

    def __init__(
        self,
        network: Network,
        pathfinder: Pathfinder,
        hops: Mapping[str, list[Hop]],
        detours: DetourPolicy,
    ) -> None:
        """Rank every zone that can reach the end zone.

        Args:
            network: The map being simulated.
            pathfinder: Answers distances.
            hops: The shortest next hops of every zone.
            detours: Answers each zone's detour hops.
        """
        self.network = network
        self._hops = hops
        keyed: list[tuple[tuple[int, bool, int, int], str]] = []
        for index, name in enumerate(network.zones):
            distance = pathfinder.distance(name)
            if distance is None:
                continue
            exits = len(hops[name]) + len(detours.detours(name))
            key = (distance, not self.is_on_priority_route(name), exits, index)
            keyed.append((key, name))
        keyed.sort()
        self._rank = {name: rank for rank, (_, name) in enumerate(keyed)}

    def rank(self, zone_name: str) -> int | None:
        """Return the zone's place in decision order.

        Returns:
            0 for the zone decided first, and so on; None if the zone
            cannot reach the end zone.
        """
        return self._rank.get(zone_name)

    def is_on_priority_route(self, zone_name: str) -> bool:
        """Return whether a drone in this zone is on the priority route.

        It is if the zone itself is a priority zone, or if its first
        shortest next hop is one (``next_hops`` lists priority zones first,
        so this means any shortest next hop is a priority zone). Priority
        zones two or more hops away are not considered.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        if self.network.get_zone(zone_name).zone_type is ZoneType.PRIORITY:
            return True
        hops = self._hops.get(zone_name, [])
        return bool(hops) and hops[0].zone.zone_type is ZoneType.PRIORITY
