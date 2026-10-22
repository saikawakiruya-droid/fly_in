"""Plane geometry for the graphical view, without pygame.

Zones that share a position are spread apart, and connections that would
run over another zone are drawn as arcs (quadratic Bezier curves) that go
round it. Positions are in pixels; y grows downwards, as on screen.
"""

import math
from collections.abc import Iterable, Mapping, Sequence

Point = tuple[int, int]
Path = list[Point]
"""A connection's line, from one end to the other, as a polyline."""

ARC_SAMPLES = 24
"""Segments of an arc's polyline; even, so its middle is a sample."""

_SPREAD_GAP = 1.1
"""Spread zones keep this many zone diameters between their centers."""

_BULGES = (2, 3, 4, 5, 6, 7, 8, 10, 12)
"""Arc heights tried, in zone radii, each on both sides in turn."""


def spread_duplicates(
    points: Mapping[str, Point], radius: int
) -> dict[str, Point]:
    """Move zones that share a position apart, around that position.

    Zones alone at their position stay where they are. ``k`` zones at the
    same position are put, in the given order, on a circle around it,
    starting on the left, far enough apart for circles of ``radius`` not
    to touch.
    """
    groups: dict[Point, list[str]] = {}
    for name, point in points.items():
        groups.setdefault(point, []).append(name)
    spread = dict(points)
    for (x, y), names in groups.items():
        if len(names) < 2:
            continue
        gap = 2 * radius * _SPREAD_GAP
        ring = gap / 2 / math.sin(math.pi / len(names))
        for index, name in enumerate(names):
            angle = math.pi + 2 * math.pi * index / len(names)
            spread[name] = (
                round(x + ring * math.cos(angle)),
                round(y + ring * math.sin(angle)),
            )
    return spread


def closest_distance(points: Iterable[Point], default: float) -> float:
    """Return the distance between the closest two distinct points.

    Points are sorted by x and each is compared only with the following
    ones that are less than the best distance away in x, so a map of
    thousands of zones takes a moment instead of minutes. ``default`` is
    returned when there are fewer than two distinct points, and is also
    the largest value returned.
    """
    ordered = sorted(set(points))
    best = default
    for index, (ax, ay) in enumerate(ordered):
        for bx, by in ordered[index + 1:]:
            if bx - ax >= best:
                break
            best = min(best, math.hypot(bx - ax, by - ay))
    return best


def arc(start: Point, end: Point, bulge: float) -> Path:
    """Return a quadratic Bezier arc from ``start`` to ``end``.

    The control point is ``bulge`` pixels from the middle of the straight
    line, so the arc's middle is ``bulge / 2`` pixels off the line. A
    positive bulge bends it to the right of the line as seen on screen
    going from ``start`` to ``end`` (y grows downwards), a negative one
    to the left. A bulge of 0 gives the
    straight line, as two points.
    """
    if bulge == 0 or start == end:
        return [start, end]
    (ax, ay), (bx, by) = start, end
    length = math.hypot(bx - ax, by - ay)
    nx, ny = (ay - by) / length, (bx - ax) / length
    cx = (ax + bx) / 2 + nx * bulge
    cy = (ay + by) / 2 + ny * bulge
    path: Path = []
    for step in range(ARC_SAMPLES + 1):
        t = step / ARC_SAMPLES
        u = 1 - t
        path.append((
            round(u * u * ax + 2 * u * t * cx + t * t * bx),
            round(u * u * ay + 2 * u * t * cy + t * t * by),
        ))
    path[0], path[-1] = start, end
    return path


def middle(path: Path) -> Point:
    """Return the point halfway along a connection's path."""
    if len(path) == 2:
        (ax, ay), (bx, by) = path
        return (ax + bx) // 2, (ay + by) // 2
    return path[len(path) // 2]


def sub_path(path: Path, start: Point, end: Point) -> Path | None:
    """Return the part of a path from ``start`` to ``end``.

    ``start`` and ``end`` are each an end of the path or its middle (where
    a drone flying toward a restricted zone is drawn), in either order.
    Returns None if one of them is not such a point.
    """
    points = path
    if len(path) == 2:
        points = [path[0], middle(path), path[1]]
    if start not in points or end not in points:
        return None
    first, last = points.index(start), points.index(end)
    if first <= last:
        return points[first:last + 1]
    return points[last:first + 1][::-1]


def distance_to_path(point: Point, path: Sequence[Point]) -> float:
    """Return the shortest distance from a point to a polyline."""
    return min(
        _distance_to_segment(point, path[i], path[i + 1])
        for i in range(len(path) - 1)
    )


def _distance_to_segment(point: Point, a: Point, b: Point) -> float:
    (px, py), (ax, ay), (bx, by) = point, a, b
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class PointGrid:
    """Zones bucketed in square cells, to find the ones near a line fast.

    Comparing every connection with every zone would take minutes on
    maps with thousands of zones; a connection only needs the zones in
    the cells its line (or arc) passes over.
    """

    def __init__(self, points: Mapping[str, Point], cell: int) -> None:
        """Bucket the points in cells of ``cell`` pixels."""
        self.cell = max(cell, 1)
        self._cells: dict[tuple[int, int], list[tuple[str, Point]]] = {}
        for name, point in points.items():
            key = (point[0] // self.cell, point[1] // self.cell)
            self._cells.setdefault(key, []).append((name, point))

    def near(
        self, path: Sequence[Point], margin: float
    ) -> list[tuple[str, Point]]:
        """Return the points within the path's box widened by ``margin``."""
        xs = [x for x, _ in path]
        ys = [y for _, y in path]
        left = int((min(xs) - margin) // self.cell)
        right = int((max(xs) + margin) // self.cell)
        top = int((min(ys) - margin) // self.cell)
        bottom = int((max(ys) + margin) // self.cell)
        found: list[tuple[str, Point]] = []
        for cx in range(left, right + 1):
            for cy in range(top, bottom + 1):
                found.extend(self._cells.get((cx, cy), ()))
        return found


def route(
    start: Point,
    end: Point,
    ends: Iterable[str],
    grid: PointGrid,
    radius: int,
    spacing: float,
    placed: list[Path],
) -> Path:
    """Return the line of a connection, bent round the zones in its way.

    The straight line is kept when every zone but its two ``ends`` is at
    least ``clearance`` away from it: ``1.2 * radius``, but never more
    than half the distance between the closest two zones (``spacing``).
    On a dense map the zones are drawn bigger than that distance, and
    without the cap every neighbour would count as in the way.

    Otherwise arcs of growing height are tried, first on the side that
    bends upwards on screen (zone labels are drawn below the zones), and
    the first that clears every zone and does not run along an arc in
    ``placed`` is used; if none does, the one that keeps furthest from
    the zones. The arc chosen is added to ``placed``, so connections
    routed later keep away from it.

    A connection from a zone to itself is drawn as a small loop above the
    zone (see ``loop``).
    """
    if start == end:
        return loop(start, radius)
    clearance = min(radius * 1.2, spacing / 2)
    skip = set(ends)
    best: Path = [start, end]
    best_gap = _gap(best, grid, skip, clearance)
    if best_gap >= clearance:
        return best
    for height in _BULGES:
        for side in _sides(start, end):
            path = arc(start, end, side * height * radius)
            gap = _gap(path, grid, skip, clearance)
            if gap >= clearance and _apart(path, placed, radius * 0.6):
                placed.append(path)
                return path
            if gap > best_gap:
                best, best_gap = path, gap
    placed.append(best)
    return best


def loop(center: Point, radius: int) -> Path:
    """Return a small closed loop sitting on top of a zone.

    The loop starts and ends at the zone's center (hidden under the zone)
    and its middle is the top of the loop, where a capacity label goes.
    """
    cx, cy = center
    size = radius * 0.6
    middle_y = cy - radius - size
    path: Path = [center]
    for step in range(ARC_SAMPLES + 1):
        angle = 2 * math.pi * step / ARC_SAMPLES
        path.append((
            round(cx + size * math.sin(angle)),
            round(middle_y + size * math.cos(angle)),
        ))
    path.append(center)
    return path


def _sides(start: Point, end: Point) -> tuple[int, int]:
    """Return the bulge signs to try, the one bending upwards first.

    A positive bulge goes towards ``(ay - by, bx - ax)``; on a vertical
    line, the side bending left is tried first.
    """
    (ax, ay), (bx, by) = start, end
    nx, ny = ay - by, bx - ax
    if ny < 0 or (ny == 0 and nx < 0):
        return 1, -1
    return -1, 1


def _apart(path: Path, placed: list[Path], gap: float) -> bool:
    """Return whether the arc keeps away from every arc already placed.

    Arcs that share an end always meet there, so two arcs only count as
    running together when more than a third of this arc's points are
    within ``gap`` of the other one.
    """
    xs = [x for x, _ in path]
    ys = [y for _, y in path]
    for other in placed:
        if (
            max(x for x, _ in other) < min(xs) - gap
            or min(x for x, _ in other) > max(xs) + gap
            or max(y for _, y in other) < min(ys) - gap
            or min(y for _, y in other) > max(ys) + gap
        ):
            continue
        close = sum(
            1 for point in path if distance_to_path(point, other) < gap
        )
        if close * 3 > len(path):
            return False
    return True


def _gap(
    path: Path, grid: PointGrid, skip: set[str], clearance: float
) -> float:
    """Return how close the path comes to a zone it does not join."""
    closest = math.inf
    for name, point in grid.near(path, clearance):
        if name not in skip:
            closest = min(closest, distance_to_path(point, path))
    return closest
