"""Tests for droneflow.visualization.geometry (no pygame needed).

Decision 2026-10-22 "draw overlapping links and zones apart"; test
design ``2026-10-22_test-design-visual-overlaps.md`` A (GE01-GE19).
"""

import itertools
import math
import random

from droneflow.visualization.geometry import (
    ARC_SAMPLES,
    Point,
    PointGrid,
    arc,
    closest_distance,
    distance_to_path,
    loop,
    middle,
    route,
    spread_duplicates,
    sub_path,
)


def centroid(points: list[Point]) -> tuple[float, float]:
    """Return the mean of the points."""
    return (
        sum(x for x, _ in points) / len(points),
        sum(y for _, y in points) / len(points),
    )


def test_single_positions_stay() -> None:
    """GE01: a zone alone at its position is not moved."""
    points = {"a": (0, 0), "b": (100, 0)}

    assert spread_duplicates(points, 10) == points


def test_two_zones_side_by_side() -> None:
    """GE02: two zones at one position go left and right of it."""
    spread = spread_duplicates({"a": (50, 50), "b": (50, 50)}, 10)

    (ax, ay), (bx, by) = spread["a"], spread["b"]
    assert ax < 50 < bx
    assert ay == by == 50
    assert bx - ax == 22


def test_many_zones_on_a_ring() -> None:
    """GE03: k zones at one position end up apart, around it."""
    names = [f"z{n}" for n in range(5)]
    spread = spread_duplicates({name: (200, 200) for name in names}, 10)

    points = [spread[name] for name in names]
    assert len(set(points)) == 5
    for a, b in itertools.combinations(points, 2):
        assert math.dist(a, b) >= 22 - 1
    cx, cy = centroid(points)
    assert math.hypot(cx - 200, cy - 200) <= 1


def test_closest_distance() -> None:
    """GE04: the closest two distinct points; repeats count once."""
    points = [(0, 0), (10, 0), (100, 100), (10, 0)]

    assert closest_distance(points, 100.0) == 10


def test_closest_distance_default() -> None:
    """GE05: the default when there is no pair closer than it."""
    assert closest_distance([(0, 0)], 100.0) == 100.0
    assert closest_distance([(0, 0), (500, 0)], 100.0) == 100.0


def test_closest_distance_matches_every_pair() -> None:
    """GE06: the sweep gives the same answer as comparing every pair."""
    rng = random.Random(7)
    points = [(rng.randint(0, 999), rng.randint(0, 999)) for _ in range(300)]
    expected = min(
        math.dist(a, b)
        for a, b in itertools.combinations(set(points), 2)
    )

    assert closest_distance(points, 1000.0) == expected


def test_no_bulge_is_straight() -> None:
    """GE07: a bulge of 0 is the straight line, as two points."""
    assert arc((0, 0), (100, 0), 0) == [(0, 0), (100, 0)]


def test_arc_shape() -> None:
    """GE08: an arc keeps its ends; its middle is half the bulge off."""
    path = arc((0, 0), (100, 0), 40)

    assert path[0] == (0, 0)
    assert path[-1] == (100, 0)
    assert len(path) == ARC_SAMPLES + 1
    assert middle(path) == (50, 20)


def test_arc_sides() -> None:
    """GE09: opposite bulges bend to opposite sides."""
    assert middle(arc((0, 0), (100, 0), 40))[1] == 20
    assert middle(arc((0, 0), (100, 0), -40))[1] == -20


def test_middle_of_a_straight_line() -> None:
    """GE10: the middle of a straight path is between its ends."""
    assert middle([(0, 0), (10, 4)]) == (5, 2)


def test_sub_path_of_an_arc() -> None:
    """GE11: from an end to the middle, the middle to an end, reversed."""
    path = arc((0, 0), (100, 0), 40)
    start, mid, end = path[0], middle(path), path[-1]

    first = sub_path(path, start, mid)
    second = sub_path(path, mid, end)
    back = sub_path(path, end, start)

    assert first is not None and second is not None and back is not None
    assert (first[0], first[-1]) == (start, mid)
    assert (second[0], second[-1]) == (mid, end)
    assert back == path[::-1]


def test_sub_path_of_a_line() -> None:
    """GE12: a straight line's middle is found too."""
    assert sub_path([(0, 0), (10, 0)], (0, 0), (5, 0)) == [(0, 0), (5, 0)]


def test_sub_path_unknown_point() -> None:
    """GE13: a point that is neither an end nor the middle gives None."""
    assert sub_path([(0, 0), (10, 0)], (1, 1), (10, 0)) is None


def test_distance_to_path() -> None:
    """GE14: to the nearest segment, its ends, or a single point."""
    line = [(0, 0), (10, 0)]

    assert distance_to_path((5, 5), line) == 5
    assert distance_to_path((20, 0), line) == 10
    assert distance_to_path((3, 4), [(0, 0), (0, 0)]) == 5


def test_point_grid_near() -> None:
    """GE15: points near the path are found, far ones are not."""
    grid = PointGrid({"near": (50, 5), "far": (50, 500)}, 20)

    names = [name for name, _ in grid.near([(0, 0), (100, 0)], 12)]

    assert "near" in names
    assert "far" not in names


def grid_of(points: dict[str, Point]) -> PointGrid:
    """Return the grid the layout would build for radius 10."""
    return PointGrid(points, 40)


def test_route_straight_when_clear() -> None:
    """GE16: nothing in the way keeps the straight line."""
    points = {"s": (0, 0), "g": (200, 0), "a": (100, 100)}

    path = route((0, 0), (200, 0), ("s", "g"), grid_of(points), 10, 100, [])

    assert path == [(0, 0), (200, 0)]


def test_route_bends_round_a_zone() -> None:
    """GE17: a zone on the line is avoided by an arc."""
    points = {"s": (0, 0), "b": (100, 0), "g": (200, 0)}

    path = route((0, 0), (200, 0), ("s", "g"), grid_of(points), 10, 100, [])

    assert len(path) > 2
    assert distance_to_path((100, 0), path) >= 12


def test_route_ignores_its_ends() -> None:
    """GE18: the two zones the connection joins are not in the way."""
    points = {"s": (0, 0), "g": (200, 0)}

    path = route((0, 0), (200, 0), ("s", "g"), grid_of(points), 10, 100, [])

    assert path == [(0, 0), (200, 0)]


def test_route_when_nothing_clears() -> None:
    """GE19: with zones everywhere, the path keeping furthest is used."""
    points = {"s": (0, 0), "g": (200, 0)}
    for x in range(0, 201, 10):
        for y in range(-300, 301, 10):
            if (x, y) not in ((0, 0), (200, 0)):
                points[f"z{x}_{y}"] = (x, y)
    others = [p for n, p in points.items() if n not in ("s", "g")]

    path = route((0, 0), (200, 0), ("s", "g"), grid_of(points), 10, 100, [])

    def gap(candidate: list[Point]) -> float:
        return min(distance_to_path(p, candidate) for p in others)

    assert gap(path) >= gap([(0, 0), (200, 0)])


def test_route_clearance_capped_by_spacing() -> None:
    """GE20: on a dense map, neighbours beside the line are not in the way.

    Zones 7 pixels apart drawn with radius 10 would all be closer than
    1.2 * radius; the cap (half the spacing) keeps the line straight, but
    a zone right on the line is still avoided.
    """
    beside = {"s": (0, 0), "g": (14, 0), "n": (7, 7)}
    on_line = {"s": (0, 0), "g": (14, 0), "m": (7, 0)}

    straight = route((0, 0), (14, 0), ("s", "g"), grid_of(beside), 10, 7, [])
    bent = route((0, 0), (14, 0), ("s", "g"), grid_of(on_line), 10, 7, [])

    assert straight == [(0, 0), (14, 0)]
    assert len(bent) > 2


def test_arcs_keep_apart() -> None:
    """GE21: connections over the same zones bend apart, not together.

    Five zones on a line joined by every connection that skips a zone:
    each arc is placed apart from the arcs placed before it.
    """
    names = "abcde"
    points = {n: (i * 100, 0) for i, n in enumerate(names)}
    grid = grid_of(points)
    placed: list[list[Point]] = []
    arcs = []
    for i, j in itertools.combinations(range(5), 2):
        if j - i < 2:
            continue
        path = route(points[names[i]], points[names[j]],
                     (names[i], names[j]), grid, 10, 100, placed)
        arcs.append(path)

    assert all(len(path) > 2 for path in arcs)
    assert len(placed) == len(arcs)
    for first, second in itertools.combinations(arcs, 2):
        close = sum(
            1 for p in second if distance_to_path(p, first) < 6
        )
        assert close * 3 <= len(second)


def test_first_arc_bends_upwards() -> None:
    """GE22: the first arc tried bends up (labels are below zones)."""
    points = {"s": (0, 100), "b": (100, 100), "g": (200, 100)}

    path = route((0, 100), (200, 100), ("s", "g"), grid_of(points), 10,
                 100, [])

    assert middle(path)[1] < 100


def test_self_loop() -> None:
    """GE23: a zone joined to itself gets a small loop above it."""
    path = route((50, 50), (50, 50), ("a", "a"), grid_of({"a": (50, 50)}),
                 10, 100, [])

    assert path == loop((50, 50), 10)
    assert path[0] == path[-1] == (50, 50)
    assert len(path) > 3
    assert all(y <= 50 for _, y in path)
    assert middle(path)[1] < 50 - 10
