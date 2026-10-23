"""GraphicalVisualizer: the run drawn turn by turn with matplotlib.

This is the only module that imports matplotlib. Zones are drawn in map
units with the radius the connections are routed round, and x and y keep
the same scale, so a connection bends only where it would cross a zone
on screen, and zooming in (matplotlib's toolbar) makes the zones bigger.
"""

import math
import time

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.artist import Artist
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.colors import is_color_like, to_rgb
from matplotlib.patches import Circle, Patch, RegularPolygon

from ..errors import VisualizationError
from ..models.drone import Drone
from ..models.network import Network
from ..models.zone import Zone, ZoneRole, ZoneType
from ..simulation.state import Move, SimulationState
from .geometry import (
    Path,
    Point,
    middle,
    route,
    spread_duplicates,
    zone_radius,
)
from .palette import rgb

Color = tuple[float, float, float]

DELAY = 0.5
"""Seconds each turn stays on screen."""
_TICK = 0.02
"""Seconds between two looks at the window's events while waiting."""

_BACKGROUND = "#181b22"
_LINK = "#555c6c"
_TEXT = "#e1e4eb"
_DRONE = "#fafafa"
_DRONE_FLYING = "#00dcff"
_OUTLINE = "#0a0a0e"
_BLOCKED_FILL = "#3c3c42"
_DEFAULT_FILL = "#8c92a0"
_ENDPOINT_RING = "#f5f5f5"
_RESTRICTED_RING = "#ff5a3c"
_PRIORITY_RING = "#ffc800"
_KEY = ("white ring: start/end   square, red ring: restricted   "
        "gold ring: priority   gray: blocked   cyan: drones in flight")
_MAX_NAMED_ZONES = 60
"""Maps with more zones are drawn without zone names."""


def zone_color(name: str | None) -> Color | str:
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
        self.paths: dict[str, Path] = {
            link.name: route(
                self.points[link.zone_a],
                self.points[link.zone_b],
                (p for name, p in self.points.items()
                 if name not in (link.zone_a, link.zone_b)),
                self.radius,
            )
            for link in network.connections
        }
        self._drones: list[Artist] = []
        axes.set_facecolor(_BACKGROUND)
        axes.set_axis_off()
        axes.set_aspect("equal", adjustable="datalim")
        axes.add_collection(LineCollection(
            list(self.paths.values()), colors=_LINK, linewidths=1.5,
            zorder=1,
        ))
        zones = list(network.zones.values())
        axes.add_collection(PatchCollection(
            [self._shape(zone) for zone in zones],
            facecolors=[_fill(zone) for zone in zones],
            edgecolors=[_ring(zone) for zone in zones],
            linewidths=2, zorder=2,
        ))
        if len(zones) <= _MAX_NAMED_ZONES:
            for zone in zones:
                x, y = self.points[zone.name]
                axes.text(x, y - self.radius * 1.15, zone.name, ha="center",
                          va="top", color=_TEXT, fontsize=8, zorder=3)
        axes.autoscale_view()
        axes.margins(0.08)

    def show(self, state: SimulationState) -> None:
        """Draw the drones of a state and its turn number.

        One drone is a dot; several at the same point are one bigger dot
        holding their number. Delivered drones stay in the end zone, and
        drones flying to a restricted zone are drawn cyan, in the middle
        of their connection.

        Args:
            state: The state to show.
        """
        for artist in self._drones:
            artist.remove()
        groups: dict[Point, list[Drone]] = {}
        for drone in state.drones.values():
            if drone.in_transit_connection is not None:
                point = middle(self.paths[drone.in_transit_connection])
            elif drone.current_zone is not None:
                point = self.points[drone.current_zone]
            else:
                continue
            groups.setdefault(point, []).append(drone)
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
        self.axes.set_title(
            f"Turn {state.turn_number}   "
            f"delivered {state.delivered_count}/{len(state.drones)}",
            loc="left", color=_TEXT,
        )

    def _shape(self, zone: Zone) -> Patch:
        """Return a zone's shape: a square if restricted, else a circle.

        Args:
            zone: The zone to draw.

        Returns:
            The shape, inside the clearance the connections keep.
        """
        center = self.points[zone.name]
        if zone.zone_type is ZoneType.RESTRICTED:
            return RegularPolygon(center, 4, radius=self.radius * 1.15,
                                  orientation=math.pi / 4)
        return Circle(center, self.radius)


def _fill(zone: Zone) -> Color | str:
    """Return a zone's fill: its color, or dark gray when blocked.

    Args:
        zone: The zone to fill.

    Returns:
        The fill color.
    """
    if zone.zone_type is ZoneType.BLOCKED:
        return _BLOCKED_FILL
    return zone_color(zone.color)


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


class GraphicalVisualizer:
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
                            facecolor=_BACKGROUND)
        if figure.canvas.required_interactive_framework is None:
            plt.close(figure)
            raise VisualizationError(
                "cannot open the graphical window (no display?)"
            )
        figure.text(0.02, 0.02, _KEY, color=_TEXT, fontsize=8)
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
