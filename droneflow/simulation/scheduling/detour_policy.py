"""DetourPolicy: which longer moves a drone that would wait may take."""

from collections.abc import Mapping

from ...pathfinding.pathfinder import Hop, Pathfinder
from .positions import PositionBoard


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
    positions the scheduler reports at the start of each turn. It keeps
    them turn by turn, so planning a turn again (or an earlier turn, for a
    new simulation) first drops what was reported for that turn and later.
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
        self._costed_detours: dict[str, list[tuple[int, Hop]]] = {
            name: self._costed(pathfinder, name) for name in hops
        }
        self._below: dict[str, set[str]] = {
            name: self._zones_below(name, hops) for name in hops
        }
        self._queue_zones: dict[str, set[str]] = {
            name: below | {name} for name, below in self._below.items()
        }
        self._reported: dict[int, dict[int, str]] = {}
        self._visited: dict[int, set[str]] = {}

    def detours(self, zone_name: str) -> list[Hop]:
        """Return the zone's detour hops, cheapest first.

        Args:
            zone_name: Name of the zone.

        Returns:
            The detour hops out of the zone (empty if it has none).

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        self.pathfinder.distance(zone_name)  # unknown names raise
        return [hop for _, hop in self._costed_detours.get(zone_name, [])]

    def remember(self, turn: int, board: PositionBoard) -> None:
        """Record where every drone is (or is landing) when ``turn`` starts.

        What was recorded for ``turn`` or a later turn is dropped first, so
        only the positions given for the turns before it count as visited.

        Args:
            turn: The turn about to be planned.
            board: Where every drone is (or is landing) at its start.
        """
        self._forget_from(turn)
        zone_names = board.zone_name_by_drone()
        self._reported[turn] = zone_names
        self._visit(zone_names)

    def _forget_from(self, turn: int) -> None:
        """Drop the positions reported for ``turn`` and later turns.

        The visited zones are then rebuilt from the earlier reports.

        Args:
            turn: The first turn whose report to drop.
        """
        if any(earlier >= turn for earlier in self._reported):
            self._reported = {
                earlier: zone_names
                for earlier, zone_names in self._reported.items()
                if earlier < turn
            }
            self._visited = {}
            for zone_names in self._reported.values():
                self._visit(zone_names)

    def _visit(self, zone_names: Mapping[int, str]) -> None:
        """Mark each drone's zone as visited by that drone.

        Args:
            zone_names: The zone name by drone_id.
        """
        for drone_id, zone_name in zone_names.items():
            self._visited.setdefault(drone_id, set()).add(zone_name)

    def allowed(
        self,
        drone_id: int,
        zone_name: str,
        board: PositionBoard,
    ) -> list[Hop]:
        """Return the detours this drone may take now, cheapest first.

        Args:
            drone_id: The drone deciding.
            zone_name: Where the drone stands.
            board: Where every drone on the map will be after the moves
                decided so far this turn (the scheduler's board).

        Returns:
            The allowed detours; empty if the zone cannot reach the end
            zone.

        Raises:
            ZoneNotFoundError: If no zone with this name exists.
        """
        distance = self.pathfinder.distance(zone_name)
        if distance is None:
            return []
        visited = self._visited.get(drone_id, set())
        candidates = [
            (total, hop) for total, hop in self._costed_detours[zone_name]
            if hop.zone.name not in visited
        ]
        if not candidates:
            return []
        budget = distance + board.count_in(self._below[zone_name])
        return [
            hop for total, hop in candidates
            if total + board.count_in(self._queue_zones[hop.zone.name])
            <= budget
        ]

    @staticmethod
    def _costed(pathfinder: Pathfinder, name: str) -> list[tuple[int, Hop]]:
        """Return the zone's detours with their total cost to the end.

        Args:
            pathfinder: Answers detour hops and route costs.
            name: Name of the zone.

        Returns:
            ``(route_cost, hop)`` pairs, in ``detour_hops`` order.
        """
        return [
            (pathfinder.route_cost(hop), hop)
            for hop in pathfinder.detour_hops(name)
        ]

    @staticmethod
    def _zones_below(name: str, hops: Mapping[str, list[Hop]]) -> set[str]:
        """Return the zones reachable from ``name`` by shortest hops.

        Args:
            name: Name of the zone to start from.
            hops: The shortest next hops of every zone.

        Returns:
            The zones below ``name`` (not including it).
        """
        below: set[str] = set()
        stack = [name]
        while stack:
            for hop in hops.get(stack.pop(), []):
                if hop.zone.name not in below:
                    below.add(hop.zone.name)
                    stack.append(hop.zone.name)
        return below
