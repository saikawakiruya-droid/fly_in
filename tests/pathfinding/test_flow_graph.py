"""Tests for droneflow.pathfinding.flow_graph (FG01-FG13).

``FlowGraph`` knows nothing about zones, so these tests build it from
plain integer vertices only. The vertex and arc numbers are the values
``add_vertex`` and ``add_arc`` return, starting at 0.
"""

import pytest

from droneflow.pathfinding.flow_graph import FlowGraph


def graph_with(vertices: int) -> tuple[FlowGraph, list[int]]:
    """Return a graph with ``vertices`` vertices and their numbers."""
    graph = FlowGraph()
    return graph, [graph.add_vertex() for _ in range(vertices)]


def one_wide_arc() -> FlowGraph:
    """Return the two-vertex graph with a single arc 0 -> 1 of 10."""
    graph, _ = graph_with(2)
    graph.add_arc(0, 1, 10)
    return graph


def cancelling_graph() -> tuple[FlowGraph, dict[str, int]]:
    """Return the graph of FG08/FG09 and its vertices by name.

    The order of vertices and arcs decides which augmenting path the
    breadth-first search finds first: s-x-y-t (three arcs) comes first,
    and the second path s-u-v-y-x-p-q-t has to cancel the flow on x->y
    through the reverse arc y->x.
    """
    graph = FlowGraph()
    v = {name: graph.add_vertex() for name in "sxytpquv"}
    for tail, head in (
        "sx", "xy", "yt", "xp", "pq", "qt", "su", "uv", "vy"
    ):
        graph.add_arc(v[tail], v[head], 1)
    return graph, v


# --- numbering --------------------------------------------------------


def test_vertices_are_numbered_from_zero() -> None:
    """FG01: add_vertex hands out 0, 1, 2 in turn."""
    graph = FlowGraph()

    assert [graph.add_vertex() for _ in range(3)] == [0, 1, 2]


def test_arcs_come_in_pairs_with_their_reverse() -> None:
    """FG02: even arcs are the ones added, ``arc ^ 1`` their reverse."""
    graph, _ = graph_with(3)

    first = graph.add_arc(0, 1, 3)
    second = graph.add_arc(1, 2, 2)

    assert (first, second) == (0, 2)
    assert graph.endpoints(0) == (0, 1)
    assert graph.endpoints(1) == (1, 0)
    assert graph.endpoints(2) == (1, 2)
    assert graph.endpoints(3) == (2, 1)
    for arc in range(4):
        tail, head = graph.endpoints(arc)
        assert graph.endpoints(arc ^ 1) == (head, tail)


# --- add_arc errors ---------------------------------------------------


def test_negative_capacity_is_rejected() -> None:
    """FG03: ValueError naming -1; nothing is added; 0 is allowed."""
    graph, _ = graph_with(2)

    with pytest.raises(ValueError, match="-1"):
        graph.add_arc(0, 1, -1)

    assert graph.add_arc(0, 1, 0) == 0


@pytest.mark.parametrize(
    ("tail", "head", "capacity", "error", "message"),
    [
        pytest.param(0, 9, 1, IndexError, "no such vertex: 9", id="head"),
        pytest.param(9, 0, 1, IndexError, "no such vertex: 9", id="tail"),
        pytest.param(
            -1, 0, 1, IndexError, "no such vertex: -1", id="negative-tail"
        ),
        pytest.param(
            0, -1, 1, IndexError, "no such vertex: -1", id="negative-head"
        ),
        pytest.param(
            -1, 0, -5, ValueError, "capacity must not be negative: -5",
            id="capacity-first",
        ),
    ],
)
def test_arc_to_a_missing_vertex_is_rejected(
    tail: int,
    head: int,
    capacity: int,
    error: type[Exception],
    message: str,
) -> None:
    """FG04: both ends are checked (negatives too), after the capacity.

    No broken arc is left behind: the next arc is still number 0.
    """
    graph, _ = graph_with(2)

    with pytest.raises(error) as excinfo:
        graph.add_arc(tail, head, capacity)

    assert str(excinfo.value) == message
    assert graph.add_arc(0, 1, 1) == 0


# --- max_flow and reachable_from --------------------------------------


def test_series_arcs_flow_the_smallest_capacity() -> None:
    """FG05: 0->1(3), 1->2(2) carry 2; the saturated arc stops the search."""
    graph, _ = graph_with(3)
    graph.add_arc(0, 1, 3)
    graph.add_arc(1, 2, 2)

    assert graph.reachable_from(0) == {0, 1, 2}
    assert graph.max_flow(0, 2, 10) == 2
    assert graph.reachable_from(0) == {0, 1}


def test_parallel_arcs_add_up() -> None:
    """FG06 a): two arcs between the same vertices carry 2 + 3."""
    graph, _ = graph_with(2)
    graph.add_arc(0, 1, 2)
    graph.add_arc(0, 1, 3)

    assert graph.max_flow(0, 1, 100) == 5


def test_parallel_paths_add_up() -> None:
    """FG06 b): s-a-t and s-b-t of capacity 1 carry 2 together."""
    graph = FlowGraph()
    s, a, b, t = (graph.add_vertex() for _ in range(4))
    graph.add_arc(s, a, 1)
    graph.add_arc(a, t, 1)
    graph.add_arc(s, b, 1)
    graph.add_arc(b, t, 1)

    assert graph.max_flow(s, t, 100) == 2


def test_empty_and_backward_arcs_carry_nothing() -> None:
    """FG07: 0->1(0) and 1->0(5): no flow, and 1 is out of reach."""
    graph, _ = graph_with(2)
    graph.add_arc(0, 1, 0)
    graph.add_arc(1, 0, 5)

    assert graph.max_flow(0, 1, 5) == 0
    assert graph.reachable_from(0) == {0}


def test_reverse_arcs_cancel_earlier_flow() -> None:
    """FG08: the second path needs y->x; without it the flow would be 1."""
    graph, v = cancelling_graph()

    assert graph.max_flow(v["s"], v["t"], 10) == 2
    assert graph.reachable_from(v["s"]) == {v["s"]}


def test_flow_stays_in_the_graph_between_calls() -> None:
    """FG09: the first path is s-x-y-t; the next call goes on from there.

    After one unit, x is reached only through the reverse arc y->x (s->x
    is saturated), so the reverse arcs gained room.
    """
    graph, v = cancelling_graph()

    assert graph.max_flow(v["s"], v["t"], 1) == 1
    assert graph.reachable_from(v["s"]) == set(v.values())
    assert v["x"] in graph.reachable_from(v["s"])
    assert graph.max_flow(v["s"], v["t"], 10) == 1
    assert graph.reachable_from(v["s"]) == {v["s"]}


def test_limit_stops_the_flow() -> None:
    """FG10: the push is cut to ``limit - flow``; the rest stays usable."""
    graph = one_wide_arc()

    assert graph.max_flow(0, 1, 4) == 4
    assert graph.reachable_from(0) == {0, 1}
    assert graph.max_flow(0, 1, 10) == 6
    assert graph.reachable_from(0) == {0}
    assert graph.max_flow(0, 1, 5) == 0


def test_limit_below_one_pushes_nothing() -> None:
    """FG11: FlowGraph does not check the limit; 0 and -2 push nothing."""
    graph = one_wide_arc()

    assert graph.max_flow(0, 1, 0) == 0
    assert graph.max_flow(0, 1, -2) == 0
    assert graph.reachable_from(0) == {0, 1}
    assert graph.max_flow(0, 1, 10) == 10


# --- max_flow errors --------------------------------------------------


@pytest.mark.parametrize(
    ("vertex", "limit"),
    [
        pytest.param(0, 3, id="vertex-0"),
        pytest.param(1, 3, id="vertex-1"),
        pytest.param(0, 0, id="limit-0"),
    ],
)
def test_source_equal_to_sink_is_rejected(vertex: int, limit: int) -> None:
    """FG12: ValueError before any flow, even with limit 0."""
    graph = one_wide_arc()

    with pytest.raises(ValueError) as excinfo:
        graph.max_flow(vertex, vertex, limit)

    assert str(excinfo.value) == (
        f"source and sink are the same vertex: {vertex}"
    )
    assert graph.reachable_from(0) == {0, 1}
    assert graph.max_flow(0, 1, 100) == 10


@pytest.mark.parametrize(
    ("source", "sink", "missing"),
    [
        pytest.param(0, 5, 5, id="sink"),
        pytest.param(5, 0, 5, id="source"),
        pytest.param(-1, 0, -1, id="negative-source"),
        pytest.param(0, -1, -1, id="negative-sink"),
        pytest.param(5, 5, 5, id="same-missing"),
    ],
)
def test_missing_source_or_sink_is_rejected(
    source: int, sink: int, missing: int
) -> None:
    """FG13: IndexError, checked before ``source == sink``; graph unchanged."""
    graph = one_wide_arc()

    with pytest.raises(IndexError) as excinfo:
        graph.max_flow(source, sink, 3)

    assert str(excinfo.value) == f"no such vertex: {missing}"
    assert graph.max_flow(0, 1, 100) == 10


def test_max_flow_on_an_empty_graph_is_rejected() -> None:
    """FG13 f): no vertex 0 at all, so IndexError rather than ValueError."""
    with pytest.raises(IndexError) as excinfo:
        FlowGraph().max_flow(0, 0, 1)

    assert str(excinfo.value) == "no such vertex: 0"
