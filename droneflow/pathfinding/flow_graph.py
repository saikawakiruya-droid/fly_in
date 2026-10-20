"""FlowGraph: a capacitated directed graph with a hand-written max flow."""

from collections import deque


class FlowGraph:
    """A directed graph whose arcs carry flow, with its residual graph.

    Vertices are the integers handed out by ``add_vertex``. Each
    ``add_arc`` stores two arcs side by side: the arc itself (even number)
    and its reverse (the next odd number), so ``arc ^ 1`` finds one from
    the other. An arc's residual capacity is how much more flow it can
    take; pushing flow along an arc gives the same amount back to its
    reverse, which is how a later path can cancel earlier flow.

    No graph libraries are used: the max flow is Edmonds-Karp (shortest
    augmenting paths found by breadth-first search).
    """

    def __init__(self) -> None:
        self._heads: list[int] = []
        self._residual: list[int] = []
        self._arcs_out: list[list[int]] = []

    def add_vertex(self) -> int:
        """Add a vertex and return its number."""
        self._arcs_out.append([])
        return len(self._arcs_out) - 1

    def add_arc(self, tail: int, head: int, capacity: int) -> int:
        """Add an arc from ``tail`` to ``head`` and return its number.

        Raises:
            ValueError: If ``capacity`` is negative.
            IndexError: If either vertex does not exist.
        """
        if capacity < 0:
            raise ValueError(f"capacity must not be negative: {capacity}")
        self._arcs_out[tail]
        self._arcs_out[head]
        arc = len(self._heads)
        self._heads.extend((head, tail))
        self._residual.extend((capacity, 0))
        self._arcs_out[tail].append(arc)
        self._arcs_out[head].append(arc ^ 1)
        return arc

    def endpoints(self, arc: int) -> tuple[int, int]:
        """Return the ``(tail, head)`` of an arc returned by ``add_arc``."""
        return self._heads[arc ^ 1], self._heads[arc]

    def max_flow(self, source: int, sink: int, limit: int) -> int:
        """Push flow from ``source`` to ``sink``, stopping at ``limit``.

        The flow stays in the graph: ``reachable_from`` then sees the
        residual graph it leaves behind.

        Returns:
            The flow pushed: the maximum flow, or ``limit`` if that is
            smaller.
        """
        flow = 0
        while flow < limit:
            path = self._augmenting_path(source, sink)
            if path is None:
                break
            push = min(min(self._residual[arc] for arc in path), limit - flow)
            for arc in path:
                self._residual[arc] -= push
                self._residual[arc ^ 1] += push
            flow += push
        return flow

    def reachable_from(self, source: int) -> set[int]:
        """Return the vertices reachable through arcs with room left."""
        seen = {source}
        queue = deque([source])
        while queue:
            vertex = queue.popleft()
            for arc in self._arcs_out[vertex]:
                head = self._heads[arc]
                if self._residual[arc] > 0 and head not in seen:
                    seen.add(head)
                    queue.append(head)
        return seen

    def _augmenting_path(self, source: int, sink: int) -> list[int] | None:
        """Return the arcs of a shortest path with room left, or None."""
        came_by: dict[int, int] = {}
        seen = {source}
        queue = deque([source])
        while queue and sink not in seen:
            vertex = queue.popleft()
            for arc in self._arcs_out[vertex]:
                head = self._heads[arc]
                if self._residual[arc] > 0 and head not in seen:
                    seen.add(head)
                    came_by[head] = arc
                    queue.append(head)
        if sink not in seen:
            return None
        path: list[int] = []
        vertex = sink
        while vertex != source:
            arc = came_by[vertex]
            path.append(arc)
            vertex = self._heads[arc ^ 1]
        return path
