"""The flow map: which routes the drones take, and how many per turn.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* Route: one path from the start zone to the end zone, and its rate.
* FlowMap: the held map (a ``Network`` cut down to the routes) and the
  routes, with the turn the last drone arrives.
* FlowGraph: the residual graph the successive shortest paths run on.
* Pathfinder: builds the ``FlowMap`` for a number of drones.
"""

from collections import deque
from dataclasses import dataclass, replace

from errors import UnreachableGoalError
from world import Connection, Network, ZoneRole, ZoneType


# --- Route ------------------------------------------------------------

@dataclass(frozen=True)
class Route:
    """One path from the start zone to the end zone.

    Attributes:
        zones: The zone names from the start zone to the end zone.
        rate: How many drones may leave the start zone along it each turn
            without any of them ever waiting on the way.
        turns: The turns a drone needs to go all the way along it (the
            sum of the turn costs of the zones it enters).
    """

    zones: tuple[str, ...]
    rate: int
    turns: int

    def arrival_turn(self, depart_turn: int) -> int:
        """Return the turn a drone leaving on ``depart_turn`` arrives.

        Args:
            depart_turn: The turn the drone leaves the start zone (1 for
                the first turn).

        Returns:
            The turn it enters the end zone.
        """
        return depart_turn + self.turns - 1


# --- FlowMap ----------------------------------------------------------

@dataclass(frozen=True)
class FlowMap:
    """The held map: only the zones and connections the routes use.

    ``network`` is a ``Network`` like the parsed one, but cut down to the
    routes, and its capacities are the number of drones the routes send
    through each zone and connection per turn (never more than the parsed
    capacities). If every route sends at most its ``rate`` each turn, no
    zone or connection of the parsed map is ever over capacity and no
    drone ever waits after leaving the start zone.

    Attributes:
        network: The held map.
        routes: The routes, shortest first (priority zones first among
            routes of the same length).
        last_turn: The turn the last of the drones arrives when every
            route sends ``rate`` drones per turn for as long as they
            arrive by then. 0 when there are no drones.
    """

    network: Network
    routes: tuple[Route, ...]
    last_turn: int


def last_turn(routes: tuple[Route, ...], nb_drones: int) -> int:
    """Return the first turn by which the routes can deliver every drone.

    A route of ``turns`` turns and rate ``r`` delivers ``r`` drones on
    every turn from turn ``turns`` on, so by turn ``T`` it has delivered
    ``r * (T - turns + 1)`` drones.

    Args:
        routes: The routes, each with at least one drone per turn.
        nb_drones: How many drones must arrive.

    Returns:
        The smallest such turn ``T``; 0 if there are no drones.

    Raises:
        ValueError: If there are drones but no route.
    """
    if nb_drones <= 0:
        return 0
    if not routes:
        raise ValueError("no route to send the drones along")
    turn = min(route.turns for route in routes)
    while sum(
        route.rate * max(0, turn - route.turns + 1) for route in routes
    ) < nb_drones:
        turn += 1
    return turn


# --- FlowGraph --------------------------------------------------------

@dataclass
class _Arc:
    """One arc of the residual graph, and the arc going back.

    Attributes:
        head: The node the arc leads to.
        room: How much more flow it can take.
        cost: The cost of one unit of flow (negative on a back arc).
        turns: The turns one drone spends on it (negative on a back arc).
        back: The index of the back arc in ``head``'s arc list.
        connection: The connection the arc stands for, or None for the arc
            inside a zone (and for back arcs).
    """

    head: int
    room: int
    cost: int
    turns: int
    back: int
    connection: Connection | None


class FlowGraph:
    """The residual graph of the map, for the successive shortest paths.

    Each zone a drone can enter is two nodes, "in" and "out", joined by an
    arc whose capacity is the zone's ``max_drones`` (the start and end
    zones are unlimited). Each connection gives an arc from the "out" node
    of each end to the "in" node of the other, with the connection's
    capacity, so a drone pays for a zone when it enters it. The start zone
    is never entered and the end zone never left, so they get no arcs in
    that direction. Blocked zones get no nodes at all.

    The cost of an arc into a zone is its turn cost, times a weight larger
    than the number of times any flow can pass through priority zones,
    minus 1 if the zone is a priority zone: among equally fast flows, the
    one through more priority zones is cheaper. Every flow found has the
    fewest turns in total, and then the most priority zones.
    """

    def __init__(self, network: Network, unlimited: int) -> None:
        """Build the graph with no flow yet.

        Args:
            network: The parsed map.
            unlimited: The capacity used for zones without a limit (the
                number of drones is enough: no more can ever pass).
        """
        self.network = network
        names = [
            name for name, zone in network.zones.items()
            if zone.zone_type.is_traversable
        ]
        self._index = {name: index for index, name in enumerate(names)}
        self._names = names
        self._arcs: list[list[_Arc]] = [[] for _ in range(2 * len(names))]
        # More than the priority zones any flow can pass through.
        self._weight = (unlimited + 1) * (len(names) + 1)
        for name in names:
            capacity = network.get_zone(name).capacity
            self._add(
                self._in(name), self._out(name),
                unlimited if capacity is None else capacity, 0, 0, None,
            )
        for connection in network.connections:
            self._add_link(connection, connection.zone_a, connection.zone_b)
            self._add_link(connection, connection.zone_b, connection.zone_a)
        self.source = self._out(network.start_zone.name)
        self.sink = self._in(network.end_zone.name)

    def shortest_path(self) -> list[_Arc] | None:
        """Return the cheapest path from the source to the sink with room.

        Back arcs cost less than nothing, so the search is Bellman-Ford
        (a queue of the nodes whose cost went down). The flow never has a
        cycle of negative cost, so it ends.

        Returns:
            The arcs of the path, from the source on; None if no path has
            room.
        """
        cost: list[int | None] = [None] * len(self._arcs)
        came: list[_Arc | None] = [None] * len(self._arcs)
        cost[self.source] = 0
        queue = deque([self.source])
        queued = {self.source}
        while queue:
            node = queue.popleft()
            queued.discard(node)
            here = cost[node]
            assert here is not None
            for arc in self._arcs[node]:
                known = cost[arc.head]
                if arc.room <= 0 or (
                    known is not None and here + arc.cost >= known
                ):
                    continue
                cost[arc.head] = here + arc.cost
                came[arc.head] = arc
                if arc.head not in queued:
                    queued.add(arc.head)
                    queue.append(arc.head)
        if cost[self.sink] is None:
            return None
        path: list[_Arc] = []
        node = self.sink
        while node != self.source:
            step = came[node]
            assert step is not None
            path.append(step)
            node = self._arcs[step.head][step.back].head
        path.reverse()
        return path

    def push(self, path: list[_Arc], amount: int) -> None:
        """Send ``amount`` more flow along the path.

        Args:
            path: A path from ``shortest_path``.
            amount: How much; at most the smallest room on the path.
        """
        for arc in path:
            arc.room -= amount
            self._arcs[arc.head][arc.back].room += amount

    def routes(self) -> tuple[Route, ...]:
        """Split the flow into routes from the start zone to the end zone.

        The flow of a connection is what its back arc has room for. A
        drone flows along a connection in one direction only: the two
        directions would cancel out at a lower cost. With every cost
        positive, the flow has no cycle, so following the flow from the
        start zone always ends in the end zone.

        Returns:
            The routes, shortest first, then through more priority zones,
            then in the order they were found.
        """
        flow: dict[tuple[str, str], int] = {}
        for name in self._names:
            for arc in self._arcs[self._out(name)]:
                if arc.connection is None:
                    continue
                back = self._arcs[arc.head][arc.back]
                if back.room > 0:
                    flow[(name, self._name_of(arc.head))] = back.room
        found: list[tuple[int, int, Route]] = []
        start = self.network.start_zone.name
        end = self.network.end_zone.name
        while any(
            amount > 0 for (tail, _), amount in flow.items() if tail == start
        ):
            zones = [start]
            while zones[-1] != end:
                zones.append(next(
                    head for (tail, head), amount in flow.items()
                    if tail == zones[-1] and amount > 0
                ))
            steps = list(zip(zones, zones[1:]))
            rate = min(flow[step] for step in steps)
            for step in steps:
                flow[step] -= rate
            entered = [self.network.get_zone(name) for name in zones[1:]]
            turns = sum(zone.zone_type.turn_cost for zone in entered)
            priority = sum(
                1 for zone in entered if zone.zone_type is ZoneType.PRIORITY
            )
            found.append((turns, -priority, Route(tuple(zones), rate, turns)))
        found.sort(key=lambda item: (item[0], item[1]))
        return tuple(route for _, _, route in found)

    def _add_link(self, connection: Connection, tail: str, head: str) -> None:
        """Add the arc for going along ``connection`` from tail to head.

        Args:
            connection: The connection.
            tail: The zone the drone leaves.
            head: The zone the drone enters.
        """
        if tail not in self._index or head not in self._index:
            return
        if self.network.get_zone(tail).role is ZoneRole.END:
            return
        zone = self.network.get_zone(head)
        if zone.role is ZoneRole.START:
            return
        turns = zone.zone_type.turn_cost
        bonus = 1 if zone.zone_type is ZoneType.PRIORITY else 0
        self._add(
            self._out(tail), self._in(head), connection.max_link_capacity,
            turns * self._weight - bonus, turns, connection,
        )

    def _add(
        self,
        tail: int,
        head: int,
        room: int,
        cost: int,
        turns: int,
        connection: Connection | None,
    ) -> None:
        """Add an arc and its back arc (no room yet).

        Args:
            tail: The node it leaves.
            head: The node it leads to.
            room: Its capacity.
            cost: The cost of one unit of flow.
            turns: The turns one drone spends on it.
            connection: The connection it stands for, if any.
        """
        forward = _Arc(head, room, cost, turns, len(self._arcs[head]),
                       connection)
        backward = _Arc(tail, 0, -cost, -turns, len(self._arcs[tail]), None)
        self._arcs[tail].append(forward)
        self._arcs[head].append(backward)

    def _in(self, name: str) -> int:
        """Return the zone's "in" node."""
        return 2 * self._index[name]

    def _out(self, name: str) -> int:
        """Return the zone's "out" node."""
        return 2 * self._index[name] + 1

    def _name_of(self, node: int) -> str:
        """Return the name of the zone a node belongs to."""
        return self._names[node // 2]


# --- Pathfinder -------------------------------------------------------

class Pathfinder:
    """Finds the routes that get every drone to the end zone soonest.

    The drones flow like a steady stream: each route takes the same number
    of drones each turn, and no more than every zone and connection on it
    can pass on, so no drone ever waits after leaving the start zone. The
    routes are found by successive shortest paths (a minimum cost flow):
    each new path adds drones per turn, but may be longer. Sending a route
    of ``turns`` turns for as long as its drones arrive by turn ``T`` is
    the best schedule for that flow (Ford and Fulkerson's temporally
    repeated flow), so paths are added while ``T`` goes down.

    Capacity is the only thing the routes share: they are fixed before the
    first turn, and the scheduler only checks that each turn follows them.
    """

    def __init__(self, network: Network) -> None:
        """Check that the end zone can be reached from the start zone.

        Args:
            network: The parsed map.

        Raises:
            UnreachableGoalError: If no path of zones that can be entered
                leads from the start zone to the end zone.
        """
        self.network = network
        start = network.start_zone
        end = network.end_zone
        if not self._reachable(start.name, end.name):
            raise UnreachableGoalError(start.name, end.name)

    def flow_map(self, nb_drones: int) -> FlowMap:
        """Build the held map for sending ``nb_drones`` drones.

        Args:
            nb_drones: How many drones leave the start zone.

        Returns:
            The held map, its routes and the turn the last drone arrives.
        """
        if nb_drones <= 0:
            return FlowMap(self._held_map(()), (), 0)
        graph = FlowGraph(self.network, nb_drones)
        best: tuple[tuple[Route, ...], int] | None = None
        sent = 0
        while sent < nb_drones:
            path = graph.shortest_path()
            if path is None:
                break
            if best is not None and sum(a.turns for a in path) >= best[1]:
                break  # this path and every later one is too long to help
            amount = min(min(arc.room for arc in path), nb_drones - sent)
            graph.push(path, amount)
            sent += amount
            routes = graph.routes()
            finish = last_turn(routes, nb_drones)
            if best is None or finish < best[1]:
                best = (routes, finish)
        assert best is not None  # the end zone is reachable
        routes, finish = best
        used = tuple(route for route in routes if route.turns <= finish)
        return FlowMap(self._held_map(used), used, finish)

    def _held_map(self, routes: tuple[Route, ...]) -> Network:
        """Return the parsed map cut down to the routes.

        Each zone keeps its name, position, type and role, and gets the
        drones per turn its routes send through it as ``max_drones`` (the
        start and end zones stay unlimited). Each connection keeps its
        ends, and gets the drones per turn its routes send along it as
        ``max_link_capacity``. Both keep declaration order.

        Args:
            routes: The routes to keep.

        Returns:
            The held map. With no route, only the start and end zones.
        """
        through: dict[str, int] = {}
        along: dict[frozenset[str], int] = {}
        for route in routes:
            for name in route.zones:
                through[name] = through.get(name, 0) + route.rate
            for step in zip(route.zones, route.zones[1:]):
                key = frozenset(step)
                along[key] = along.get(key, 0) + route.rate
        held = Network()
        for name, zone in self.network.zones.items():
            if zone.role is not ZoneRole.HUB:
                held.add_zone(zone)
            elif name in through:
                held.add_zone(replace(zone, max_drones=through[name]))
        for connection in self.network.connections:
            key = frozenset((connection.zone_a, connection.zone_b))
            if key in along:
                held.add_connection(
                    replace(connection, max_link_capacity=along[key])
                )
        return held

    def _reachable(self, start: str, end: str) -> bool:
        """Return whether the end zone can be reached from the start zone.

        Args:
            start: The start zone's name.
            end: The end zone's name.

        Returns:
            True if a path of zones that can be entered links them.
        """
        seen = {start}
        stack = [start]
        while stack:
            name = stack.pop()
            if name == end:
                return True
            for connection in self.network.neighbors(name):
                other = connection.other_end(name)
                zone = self.network.get_zone(other)
                if other not in seen and zone.zone_type.is_traversable:
                    seen.add(other)
                    stack.append(other)
        return False
