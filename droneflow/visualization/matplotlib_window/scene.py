"""MapScene: the network and its drones drawn on a matplotlib axes.

Zones are drawn in map units with the radius the connections are routed
round, and x and y keep the same scale, so a connection bends only where
it would cross a zone on screen, and zooming in (matplotlib's toolbar)
makes the zones bigger.
"""

import math

from matplotlib.axes import Axes
from matplotlib.artist import Artist
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.colors import is_color_like, to_rgb
from matplotlib.patches import Circle, Patch, RegularPolygon

from ...models.drone import Drone
from ...models.network import Network
from ...models.zone import Zone, ZoneRole, ZoneType
from ...simulation.state import SimulationState
from ..palette import rgb
from .geometry import (
    Path,
    Point,
    middle,
    route,
    spread_duplicates,
    zone_radius,
)

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


def _zone_color(name: str | None) -> Color | str:
    """Return a zone's fill for its ``color=`` value.

    Args:
        name: The color name from the map, or None.

    Returns:
        The palette's color, else matplotlib's color of that name, else
        a neutral gray.
    """
    known = rgb(name)
    if known is not None:
        return known[0] / 255, known[1] / 255, known[2] / 255
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
