"""Plane geometry for the graphical view, without matplotlib.

Zones that share a position are spread apart, and a connection is drawn
as a straight line unless that line would cross a zone it does not join;
then it is drawn as an arc (a quadratic Bezier curve) that goes round the
zone. Positions are map units, y pointing up. The view draws every zone
with the radius used here, so a connection bends only where it would
cross a zone on screen.
"""

import math
from collections.abc import Iterable, Mapping

Point = tuple[float, float]
Path = list[Point]
"""A connection's line, from one end to the other, as a polyline."""

ARC_SAMPLES = 24
"""Segments of an arc's polyline; even, so its middle is a sample."""

CLEARANCE = 1.2
"""A line closer than this many zone radii to a zone's center bends."""

_SPREAD_GAP = 1.1
"""Spread zones keep this many zone diameters between their centers."""

_BULGES = (2, 3, 4, 6, 8, 12)
"""Arc heights tried, in zone radii, each on both sides in turn."""


def zone_radius(points: Iterable[Point]) -> float:
    """Return the radius zones are drawn with: 0.3 of the closest gap.

    Args:
        points: Every zone's position from the map.

    Returns:
        0.3 times the distance between the closest two distinct points
        (at most 1, the radius used when there are fewer than two).
    """
    ordered = sorted(set(points))
    closest = 1.0
    for index, (ax, ay) in enumerate(ordered):
        for bx, by in ordered[index + 1:]:
            if bx - ax >= closest:
                break
            closest = min(closest, math.hypot(bx - ax, by - ay))
    return 0.3 * closest


def spread_duplicates(
    points: Mapping[str, Point], radius: float
) -> dict[str, Point]:
    """Move zones that share a position apart, on a circle around it.

    Args:
        points: Each zone's position, by zone name.
        radius: The radius zones are drawn with.

    Returns:
        A new mapping; zones alone at their position do not move.
    """
    groups: dict[Point, list[str]] = {}
    for name, point in points.items():
        groups.setdefault(point, []).append(name)
    spread = dict(points)
    for (x, y), names in groups.items():
        if len(names) < 2:
            continue
        ring = radius * _SPREAD_GAP / math.sin(math.pi / len(names))
        for index, name in enumerate(names):
            angle = math.pi + 2 * math.pi * index / len(names)
            spread[name] = (
                x + ring * math.cos(angle), y + ring * math.sin(angle)
            )
    return spread


def route(
    start: Point, end: Point, others: Iterable[Point], radius: float
) -> Path:
    """Return a connection's line, bent round the zones in its way.

    The straight line is kept when every other zone is at least
    ``CLEARANCE`` radii from it. Otherwise arcs of growing height are
    tried, bending upwards first (names are written below the zones), and
    the first that clears every zone is used; if none does, the one that
    keeps furthest from them. A connection from a zone to itself is a
    small loop above the zone.

    Args:
        start: The position of one end zone.
        end: The position of the other end zone.
        others: The positions of every zone but the two ends.
        radius: The radius zones are drawn with.

    Returns:
        The straight line (two points), an arc, or a loop.
    """
    if start == end:
        return loop(start, radius)
    others = list(others)
    clearance = radius * CLEARANCE
    best: Path = [start, end]
    best_gap = _gap(best, others)
    if best_gap >= clearance:
        return best
    upwards = 1 if end[0] >= start[0] else -1
    for height in _BULGES:
        for side in (upwards, -upwards):
            path = arc(start, end, side * height * radius)
            gap = _gap(path, others)
            if gap >= clearance:
                return path
            if gap > best_gap:
                best, best_gap = path, gap
    return best


def arc(start: Point, end: Point, bulge: float) -> Path:
    """Return a quadratic Bezier arc from ``start`` to ``end``.

    The control point is ``bulge`` from the middle of the straight line,
    on its left going from ``start`` to ``end`` (on its right when
    negative), so the arc's middle is ``bulge / 2`` off the line.

    Args:
        start: Where the arc begins.
        end: Where the arc ends; not ``start``.
        bulge: Distance of the control point from the line.

    Returns:
        The arc as ``ARC_SAMPLES + 1`` points.
    """
    (ax, ay), (bx, by) = start, end
    length = math.hypot(bx - ax, by - ay)
    cx = (ax + bx) / 2 + (ay - by) / length * bulge
    cy = (ay + by) / 2 + (bx - ax) / length * bulge
    path: Path = []
    for step in range(ARC_SAMPLES + 1):
        t = step / ARC_SAMPLES
        u = 1 - t
        path.append((
            u * u * ax + 2 * u * t * cx + t * t * bx,
            u * u * ay + 2 * u * t * cy + t * t * by,
        ))
    return path


def loop(center: Point, radius: float) -> Path:
    """Return a small closed loop sitting on top of a zone.

    Args:
        center: The zone's position.
        radius: The radius zones are drawn with.

    Returns:
        A closed polyline from the zone's top round the loop and back;
        its middle sample is the top of the loop.
    """
    cx, cy = center
    size = radius * 0.6
    middle_y = cy + radius + size
    return [
        (
            cx + size * math.sin(2 * math.pi * step / ARC_SAMPLES),
            middle_y - size * math.cos(2 * math.pi * step / ARC_SAMPLES),
        )
        for step in range(ARC_SAMPLES + 1)
    ]


def middle(path: Path) -> Point:
    """Return the point halfway along a connection's path.

    Args:
        path: A straight line (two points), an arc or a loop.

    Returns:
        The middle of a straight line, or the middle sample otherwise.
    """
    if len(path) == 2:
        (ax, ay), (bx, by) = path
        return (ax + bx) / 2, (ay + by) / 2
    return path[len(path) // 2]


def _gap(path: Path, points: list[Point]) -> float:
    """Return how close the path comes to any of the points.

    Args:
        path: The polyline, at least two points.
        points: The zone positions to measure.

    Returns:
        The smallest distance, or infinity if there are no points.
    """
    return min(
        (
            _distance_to_segment(point, path[i], path[i + 1])
            for point in points
            for i in range(len(path) - 1)
        ),
        default=math.inf,
    )


def _distance_to_segment(point: Point, a: Point, b: Point) -> float:
    """Return the shortest distance from a point to a line segment.

    Args:
        point: The point to measure from.
        a: One end of the segment.
        b: The other end of the segment.

    Returns:
        The distance to the closest point of the segment.
    """
    (px, py), (ax, ay), (bx, by) = point, a, b
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
