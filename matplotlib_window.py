"""The run drawn in a matplotlib window (``--matplotlib-window``).

Three parts, in the order they delegate:

* ``MatplotlibWindowVisualizer``: the window, one turn every ``delay``. It
  holds a ``MapScene`` and the key to its colors.
* ``MapScene``: the network and its drones drawn on a matplotlib axes.
  Zones are drawn in map units with the radius the connections are routed
  round, and x and y keep the same scale, so a connection bends only where
  it would cross a zone on screen, and zooming in (matplotlib's toolbar)
  makes the zones bigger.
* Plane geometry (``zone_radius`` to ``middle``): zones that share a
  position are spread apart, and a connection is drawn as a straight line
  unless that line would cross a zone it does not join; then it is drawn
  as an arc (a quadratic Bezier curve) that goes round the zone. Positions
  are map units, y pointing up.

``app`` imports this module only when ``--matplotlib-window`` is given, so
the program runs without matplotlib otherwise.
"""

import math
import time
from collections.abc import Iterable, Mapping

import matplotlib.pyplot as plt
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.colors import is_color_like, to_rgb
from matplotlib.patches import Circle, Patch, RegularPolygon

from engine_state import Move, SimulationState
from engine_state_drone import Drone
from errors import VisualizationError
from world_network import Network
from world_network_zone import Zone, ZoneRole, ZoneType


# --- types and settings -----------------------------------------------

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

Color = tuple[float, float, float]

BACKGROUND = "#181b22"
"""The scene's background, shared with the window around it."""
_LINK = "#555c6c"
_LINK_WIDTH = 1.5
TEXT = "#e1e4eb"
"""Color of every text, in the scene and in the window."""
_DRONE = "#fafafa"
_DRONE_FLYING = "#00dcff"
_OUTLINE = "#0a0a0e"
_BLOCKED_FILL = "#3c3c42"
_DEFAULT_FILL = "#8c92a0"
_ENDPOINT_RING = "#f5f5f5"
_RESTRICTED_RING = "#ff5a3c"
_PRIORITY_RING = "#ffc800"
KEY = ("white ring: start/end   square, red ring: restricted   "
       "gold ring: priority   gray: blocked   "
       "cyan: drones in flight and their connection")
"""What the colors and shapes mean, for the window to show."""
_MAX_NAMED_ZONES = 60
"""Maps with more zones are drawn without zone names."""
_SQUARE_REACH = 1.15
"""The restricted square's corner reach, in zone radii; names are drawn just
below it."""


# --- the window -------------------------------------------------------

DELAY = 0.5
"""Seconds each turn stays on screen."""
_TICK = 0.02
"""Seconds between two looks at the window's events while waiting."""


class MatplotlibWindowVisualizer:
    """Shows the run in a matplotlib window, one turn every ``delay``.

    The window opens when the view is made. Closing it stops the drawing
    and the waiting; the simulation then finishes at once, so the turn
    log is still complete. After a finished run the window stays open
    until it is closed.

    Attributes:
        figure: The window's figure.
        scene: The network drawn in it.
        delay: Seconds each turn stays on screen.
    """

    def __init__(self, network: Network, delay: float = DELAY) -> None:
        """Open the window and draw the network.

        Args:
            network: The network to draw.
            delay: Seconds each turn stays on screen.

        Raises:
            VisualizationError: If matplotlib cannot show a window (for
                example when there is no display).
        """
        figure = plt.figure("Fly-in", figsize=(10, 7),
                            facecolor=BACKGROUND)
        if figure.canvas.required_interactive_framework is None:
            plt.close(figure)
            raise VisualizationError(
                "cannot open the matplotlib window (no display?)"
            )
        figure.text(0.02, 0.02, KEY, color=TEXT, fontsize=8)
        self.figure = figure
        self.scene = MapScene(figure.add_axes((0.02, 0.06, 0.96, 0.88)),
                              network)
        self.delay = delay
        self._finished = False
        figure.show()

    @property
    def is_open(self) -> bool:
        """Return whether the window is still on screen."""
        return plt.fignum_exists(self.figure.number)

    def begin(self, state: SimulationState) -> None:
        """Show the initial state.

        Args:
            state: The state before the first turn.
        """
        self._show(state)

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Show the state after a turn.

        Args:
            state: The state after the turn.
            moves: The moves of the turn (not drawn).
        """
        self._show(state)

    def close(self) -> None:
        """Keep a finished run on screen until closed, then close."""
        if self._finished and self.is_open:
            plt.show()
        plt.close(self.figure)

    def _show(self, state: SimulationState) -> None:
        """Draw a state, then wait ``delay`` while handling the window.

        Nothing is drawn once the window is closed.

        Args:
            state: The state to draw.
        """
        if not self.is_open:
            return
        self.scene.show(state)
        self._finished = state.is_complete
        canvas = self.figure.canvas
        canvas.draw_idle()
        deadline = time.monotonic() + self.delay
        while self.is_open and time.monotonic() < deadline:
            canvas.start_event_loop(_TICK)


# --- the scene --------------------------------------------------------

def _zone_color(name: str | None) -> Color | str:
    """Return a zone's fill for its ``color=`` value.

    Args:
        name: The color name from the map, or None.

    Returns:
        matplotlib's color of that name (ignoring case), else a neutral
        gray.
    """
    if name is not None and is_color_like(name.lower()):
        return to_rgb(name.lower())
    return _DEFAULT_FILL


class MapScene:
    """The network drawn on an axes, and the drones redrawn each turn.

    Attributes:
        lines: Every connection's line, in ``network.connections`` order.
        points: Each zone's center, in map units (shared positions are
            spread apart).
        radius: The radius every zone is drawn with, in map units.
        paths: Each connection's line, by connection name.
    """

    def __init__(self, axes: Axes, network: Network) -> None:
        """Draw the connections, the zones and their names.

        Args:
            axes: The axes to draw on.
            network: The network to draw.
        """
        self.axes = axes
        self.radius = zone_radius(
            (z.x, z.y) for z in network.zones.values()
        )
        self.points = spread_duplicates(
            {z.name: (z.x, z.y) for z in network.zones.values()},
            self.radius,
        )
        self.paths = self._route_connections(network)
        self._drones: list[Artist] = []
        self._links = list(network.connections)
        axes.set_facecolor(BACKGROUND)
        axes.set_axis_off()
        axes.set_aspect("equal", adjustable="datalim")
        self.lines = LineCollection(
            list(self.paths.values()), colors=_LINK, linewidths=_LINK_WIDTH,
            zorder=1,
        )
        axes.add_collection(self.lines)
        zones = list(network.zones.values())
        self._draw_zones(zones)
        self._draw_zone_names(zones)
        axes.autoscale_view()
        axes.margins(0.08)

    def show(self, state: SimulationState) -> None:
        """Draw the drones of a state and its turn number.

        One drone is a dot; several at the same point are one bigger dot
        holding their number. Delivered drones stay in the end zone, and
        drones flying to a restricted zone are drawn cyan, in the middle
        of their connection, which is drawn cyan and twice as thick.

        Args:
            state: The state to show.
        """
        self._highlight_busy_links(state)
        self._draw_drones(self._drone_groups(state))
        self._draw_title(state)

    def _route_connections(self, network: Network) -> dict[str, Path]:
        """Route every connection round the zones it does not join.

        Args:
            network: The network whose connections to route.

        Returns:
            Each connection's line, by connection name.
        """
        return {
            link.name: route(
                self.points[link.zone_a],
                self.points[link.zone_b],
                (p for name, p in self.points.items()
                 if name not in (link.zone_a, link.zone_b)),
                self.radius,
            )
            for link in network.connections
        }

    def _draw_zones(self, zones: list[Zone]) -> None:
        """Draw each zone in its shape, fill and outline color.

        Args:
            zones: The zones to draw.
        """
        self.axes.add_collection(PatchCollection(
            [self._shape(zone) for zone in zones],
            facecolors=[_fill(zone) for zone in zones],
            edgecolors=[_ring(zone) for zone in zones],
            linewidths=2, zorder=2,
        ))

    def _shape(self, zone: Zone) -> Patch:
        """Return a zone's shape: a square if restricted, else a circle.

        Args:
            zone: The zone to draw.

        Returns:
            The shape, inside the clearance the connections keep.
        """
        center = self.points[zone.name]
        if zone.zone_type is ZoneType.RESTRICTED:
            return RegularPolygon(center, 4,
                                  radius=self.radius * _SQUARE_REACH,
                                  orientation=math.pi / 4)
        return Circle(center, self.radius)

    def _draw_zone_names(self, zones: list[Zone]) -> None:
        """Write each zone's name under it, if at most ``_MAX_NAMED_ZONES``.

        Args:
            zones: The zones to name.
        """
        if len(zones) <= _MAX_NAMED_ZONES:
            for zone in zones:
                x, y = self.points[zone.name]
                self.axes.text(x, y - self.radius * _SQUARE_REACH, zone.name,
                               ha="center", va="top", color=TEXT,
                               fontsize=8, zorder=3)

    def _highlight_busy_links(self, state: SimulationState) -> None:
        """Draw the connections with drones in flight cyan and twice as thick.

        Args:
            state: The state whose connection loads to show.
        """
        busy = [state.link_load(link) > 0 for link in self._links]
        self.lines.set_color([_DRONE_FLYING if b else _LINK for b in busy])
        self.lines.set_linewidth(
            [_LINK_WIDTH * 2 if b else _LINK_WIDTH for b in busy]
        )

    def _drone_groups(
        self, state: SimulationState
    ) -> dict[Point, list[Drone]]:
        """Group the drones by the point they are drawn at.

        Args:
            state: The state whose drones to group.

        Returns:
            The drones at each point: the middle of the connection for a
            drone in flight, else the center of its zone. Drones that are
            in neither are left out.
        """
        groups: dict[Point, list[Drone]] = {}
        for drone in state.drones.values():
            if drone.in_transit_connection is not None:
                point = middle(self.paths[drone.in_transit_connection])
            elif drone.current_zone is not None:
                point = self.points[drone.current_zone]
            else:
                continue
            groups.setdefault(point, []).append(drone)
        return groups

    def _draw_drones(self, groups: dict[Point, list[Drone]]) -> None:
        """Replace the drones drawn before with one dot per group.

        A group of several drones is a bigger dot holding their number.

        Args:
            groups: The drones at each point.
        """
        for artist in self._drones:
            artist.remove()
        self._drones = []
        for (x, y), drones in groups.items():
            flying = drones[0].in_transit_connection is not None
            self._drones.append(self.axes.scatter(
                [x], [y], s=40 if len(drones) == 1 else 170,
                c=_DRONE_FLYING if flying else _DRONE,
                edgecolors=_OUTLINE, zorder=4,
            ))
            if len(drones) > 1:
                self._drones.append(self.axes.text(
                    x, y, str(len(drones)), ha="center", va="center",
                    color=_OUTLINE, fontsize=7, zorder=5,
                ))

    def _draw_title(self, state: SimulationState) -> None:
        """Write the turn number and the delivered count above the map.

        Args:
            state: The state whose numbers to write.
        """
        self.axes.set_title(
            f"Turn {state.turn_number}   "
            f"delivered {state.delivered_count}/{len(state.drones)}",
            loc="left", color=TEXT,
        )


def _fill(zone: Zone) -> Color | str:
    """Return a zone's fill: its color, or dark gray when blocked.

    Args:
        zone: The zone to fill.

    Returns:
        The fill color.
    """
    if zone.zone_type is ZoneType.BLOCKED:
        return _BLOCKED_FILL
    return _zone_color(zone.color)


def _ring(zone: Zone) -> str:
    """Return the color of a zone's outline, which marks its kind.

    Args:
        zone: The zone to outline.

    Returns:
        White for the start and end, red for restricted, gold for
        priority, dark otherwise.
    """
    if zone.role in (ZoneRole.START, ZoneRole.END):
        return _ENDPOINT_RING
    if zone.zone_type is ZoneType.RESTRICTED:
        return _RESTRICTED_RING
    if zone.zone_type is ZoneType.PRIORITY:
        return _PRIORITY_RING
    return _OUTLINE


# --- plane geometry ---------------------------------------------------

def zone_radius(points: Iterable[Point]) -> float:
    """Return the radius zones are drawn with: 0.3 of the closest gap.

    Args:
        points: Every zone's position from the map.

    Returns:
        0.3 times the distance between the closest two distinct points,
        a distance over 1 (or no second point) counting as 1.
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
