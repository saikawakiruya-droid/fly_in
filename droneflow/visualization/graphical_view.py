"""GraphicalVisualizer: optional graphical rendering of the simulation.

This is the only module that imports pygame (pygame-ce); the rest of the
package works without it. Nothing is opened until the first ``begin`` or
``render`` call.
"""

import math
import os

# pygame prints a banner to standard output on import, which would corrupt
# the turn log; this must be set before the import below.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from ..models.connection import Connection  # noqa: E402
from ..models.drone import Drone  # noqa: E402
from ..models.network import Network  # noqa: E402
from ..models.zone import Zone, ZoneRole, ZoneType  # noqa: E402
from ..simulation.state import Move, SimulationState  # noqa: E402
from .palette import DEFAULT_ZONE_RGB, RGB, rgb  # noqa: E402

Point = tuple[int, int]

_BACKGROUND: RGB = (24, 27, 34)
_LINK: RGB = (85, 92, 108)
_LINK_BUSY: RGB = (150, 160, 185)
_TEXT: RGB = (225, 228, 235)
_TEXT_DIM: RGB = (140, 146, 160)
_TRAIL: RGB = (255, 215, 0)
_DRONE: RGB = (250, 250, 250)
_DRONE_MOVED: RGB = (255, 215, 0)
_DRONE_FLYING: RGB = (0, 220, 255)
_OUTLINE: RGB = (10, 10, 14)
_PRIORITY_RING: RGB = (255, 200, 0)
_RESTRICTED_RING: RGB = (255, 90, 60)
_ENDPOINT_RING: RGB = (245, 245, 245)
_BLOCKED_FILL: RGB = (60, 60, 66)
_BAR_EMPTY: RGB = (55, 60, 72)

_HUD_HEIGHT = 34
_FOOTER_HEIGHT = 26
_MARGIN = 60
_FPS = 60
_MAX_DOTS = 12
_MIN_DELAY = 0.05
_MAX_DELAY = 5.0
_MAX_STRETCH = 2.0
_LABEL_ROOM = 72
_HELP = "space: pause  right: step  up/down: speed  esc: quit"


class _Layout:
    """Maps zone coordinates to window pixels, scaled to fit.

    The map's y axis points up (math orientation): a larger y is drawn
    higher in the window.

    Each axis is scaled to fill the window, but one axis is never
    stretched more than ``_MAX_STRETCH`` times the other, so long flat
    maps get room for their labels without losing their shape entirely.
    """

    def __init__(self, network: Network, size: Point) -> None:
        """Fit every zone inside the window, below the status bar."""
        zones = list(network.zones.values())
        width, height = size
        left, right = _MARGIN, width - _MARGIN
        top = _HUD_HEIGHT + _MARGIN // 2
        bottom = height - _FOOTER_HEIGHT - _LABEL_ROOM
        min_x = min((z.x for z in zones), default=0)
        max_y = max((z.y for z in zones), default=0)
        span_x = max((z.x for z in zones), default=0) - min_x
        span_y = max_y - min((z.y for z in zones), default=0)
        scale_x = (right - left) / span_x if span_x else math.inf
        scale_y = (bottom - top) / span_y if span_y else math.inf
        if math.isinf(scale_x) and math.isinf(scale_y):
            scale_x = scale_y = 1.0
        scale_x = min(scale_x, scale_y * _MAX_STRETCH)
        scale_y = min(scale_y, scale_x * _MAX_STRETCH)
        offset_x = (left + right - span_x * scale_x) / 2
        offset_y = (top + bottom - span_y * scale_y) / 2
        self._points: dict[str, Point] = {
            z.name: (
                round(offset_x + (z.x - min_x) * scale_x),
                round(offset_y + (max_y - z.y) * scale_y),
            )
            for z in zones
        }
        self.spacing = self._closest_distance()
        self.radius = int(max(9, min(28, self.spacing * 0.3)))

    def position(self, zone_name: str) -> Point:
        """Return the pixel center of a zone."""
        return self._points[zone_name]

    def midpoint(self, connection: Connection) -> Point:
        """Return the pixel middle of a connection."""
        ax, ay = self.position(connection.zone_a)
        bx, by = self.position(connection.zone_b)
        return (ax + bx) // 2, (ay + by) // 2

    def zone_at(self, point: Point) -> str | None:
        """Return the zone drawn under a pixel, if any."""
        px, py = point
        for name, (x, y) in self._points.items():
            if math.hypot(px - x, py - y) <= self.radius:
                return name
        return None

    def _closest_distance(self) -> float:
        """Return the distance between the closest two distinct points."""
        points = list(set(self._points.values()))
        closest = 100.0
        for index, (ax, ay) in enumerate(points):
            for bx, by in points[index + 1:]:
                closest = min(closest, math.hypot(ax - bx, ay - by))
        return closest


def zone_rgb(color_name: str | None) -> RGB:
    """Return a zone's display color: palette, then pygame's names.

    Unknown names and a missing color give ``DEFAULT_ZONE_RGB``.
    """
    known = rgb(color_name)
    if known is not None:
        return known
    if color_name is not None:
        try:
            color = pygame.Color(color_name.lower())
        except ValueError:
            return DEFAULT_ZONE_RGB
        return color.r, color.g, color.b
    return DEFAULT_ZONE_RGB


class _Window:
    """The pygame window: drawing one frame and waiting between turns."""

    def __init__(self, network: Network, size: Point, delay: float) -> None:
        """Open the window and prepare fonts and the layout."""
        pygame.display.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode(size)
        pygame.display.set_caption("Fly-in")
        self.layout = _Layout(network, size)
        self.font = pygame.font.Font(None, 18)
        self.big_font = pygame.font.Font(None, 26)
        self.clock = pygame.time.Clock()
        self.links: dict[str, Connection] = {
            c.name: c for c in network.connections
        }
        self.delay = delay
        self.paused = False
        self._frame: tuple[SimulationState, list[Move], str] | None = None
        self._trails: list[tuple[Point, Point]] = []
        self._hover: tuple[str, Point] | None = None

    def drone_point(self, drone: Drone) -> Point | None:
        """Return where a drone is drawn, or None once delivered."""
        if drone.in_transit_connection is not None:
            link = self.links.get(drone.in_transit_connection)
            return None if link is None else self.layout.midpoint(link)
        if drone.current_zone is None or drone.is_delivered:
            return None
        return self.layout.position(drone.current_zone)

    def show(
        self,
        state: SimulationState,
        moves: list[Move],
        trails: list[tuple[Point, Point]],
        note: str = "",
    ) -> None:
        """Draw a frame and remember it, so it can be redrawn later."""
        self._frame = (state, moves, note)
        self._trails = trails
        self.redraw()

    def redraw(self, note: str | None = None) -> None:
        """Draw the remembered frame again, optionally with a new note."""
        if self._frame is None:
            return
        if note is not None:
            self._frame = (self._frame[0], self._frame[1], note)
        state, moves, shown_note = self._frame
        self.screen.fill(_BACKGROUND)
        self._draw_links(state)
        for start, end in self._trails:
            pygame.draw.line(self.screen, _TRAIL, start, end, 3)
        for zone in state.network.zones.values():
            self._draw_zone(state, zone)
        self._draw_drones(state, {m.drone_id for m in moves})
        self._draw_status(state, moves, shown_note)
        if self._hover is not None:
            self._draw_tooltip(state, *self._hover)
        pygame.display.flip()

    def wait(self) -> bool:
        """Wait the turn delay while handling input.

        Returns:
            False if the user asked to quit, True to go on.
        """
        deadline = pygame.time.get_ticks() + int(self.delay * 1000)
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.MOUSEMOTION:
                    self._track_mouse(event.pos)
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    return False
                if event.key == pygame.K_RIGHT:
                    return True
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                    deadline = pygame.time.get_ticks() + int(
                        self.delay * 1000
                    )
                elif event.key in (pygame.K_UP, pygame.K_PLUS,
                                   pygame.K_EQUALS, pygame.K_KP_PLUS):
                    self.delay = max(_MIN_DELAY, self.delay / 2)
                elif event.key in (pygame.K_DOWN, pygame.K_MINUS,
                                   pygame.K_KP_MINUS):
                    self.delay = min(_MAX_DELAY, self.delay * 2)
                self.redraw()
            if not self.paused and pygame.time.get_ticks() >= deadline:
                return True
            self.clock.tick(_FPS)

    def wait_for_quit(self) -> None:
        """Keep the last frame on screen until the window is closed."""
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN
                    and event.key in (pygame.K_ESCAPE, pygame.K_q)
                ):
                    return
                if event.type == pygame.MOUSEMOTION:
                    self._track_mouse(event.pos)
            self.clock.tick(_FPS)

    @staticmethod
    def close() -> None:
        """Close the window and shut pygame's display down."""
        pygame.display.quit()
        pygame.font.quit()

    def _track_mouse(self, position: Point) -> None:
        """Show details of the zone under the mouse, if it changed."""
        name = self.layout.zone_at(position)
        hover = None if name is None else (name, position)
        old = None if self._hover is None else self._hover[0]
        self._hover = hover
        if name != old or name is not None:
            self.redraw()

    def _draw_links(self, state: SimulationState) -> None:
        for link in state.network.connections:
            start = self.layout.position(link.zone_a)
            end = self.layout.position(link.zone_b)
            busy = state.link_load(link) > 0
            width = 1 + min(link.max_link_capacity, 4)
            color = _LINK_BUSY if busy else _LINK
            pygame.draw.line(self.screen, color, start, end, width)
            if link.max_link_capacity > 1:
                mid_x, mid_y = self.layout.midpoint(link)
                self._text(
                    f"x{link.max_link_capacity}",
                    (mid_x + 6, mid_y - 14),
                    _TEXT_DIM,
                )

    def _draw_zone(self, state: SimulationState, zone: Zone) -> None:
        center = self.layout.position(zone.name)
        radius = self.layout.radius
        fill = zone_rgb(zone.color)
        if zone.zone_type is ZoneType.BLOCKED:
            fill = _BLOCKED_FILL
        if zone.zone_type is ZoneType.RESTRICTED:
            rect = pygame.Rect(0, 0, radius * 2, radius * 2)
            rect.center = center
            pygame.draw.rect(self.screen, fill, rect)
            pygame.draw.rect(self.screen, _RESTRICTED_RING, rect, 3)
        else:
            pygame.draw.circle(self.screen, fill, center, radius)
            ring = _OUTLINE
            if zone.zone_type is ZoneType.PRIORITY:
                ring = _PRIORITY_RING
            if zone.has_unlimited_capacity:
                ring = _ENDPOINT_RING
            pygame.draw.circle(self.screen, ring, center, radius, 3)
        if zone.zone_type is ZoneType.BLOCKED:
            self._draw_cross(center, radius)
        self._draw_fill_bar(state, zone, center, radius)
        label = self._fit(zone.name, max(int(self.layout.spacing) - 8, 24))
        self._text(label, (center[0], center[1] + radius + 16), _TEXT, True)

    def _draw_cross(self, center: Point, radius: int) -> None:
        cx, cy = center
        size = int(radius * 0.6)
        for dx in (-size, size):
            pygame.draw.line(
                self.screen, _RESTRICTED_RING,
                (cx - dx, cy - size), (cx + dx, cy + size), 3,
            )

    def _draw_fill_bar(
        self, state: SimulationState, zone: Zone, center: Point, radius: int
    ) -> None:
        """Draw the zone's load against its capacity under the zone."""
        top = center[1] + radius + 3
        if zone.zone_type is ZoneType.BLOCKED:
            return
        if zone.role is ZoneRole.END:
            label = f"{state.delivered_count} in"
        elif zone.max_drones is None:
            label = str(state.occupancy(zone.name))
        else:
            load = state.load(zone.name)
            fraction = min(load / zone.max_drones, 1.0)
            bar = pygame.Rect(center[0] - radius, top, radius * 2, 6)
            pygame.draw.rect(self.screen, _BAR_EMPTY, bar)
            if fraction > 0:
                filled = bar.copy()
                filled.width = max(1, round(bar.width * fraction))
                pygame.draw.rect(self.screen, _load_color(fraction), filled)
            label = f"{load}/{zone.max_drones}"
        self._text(label, (center[0], top + 26), _TEXT_DIM, True)

    def _draw_drones(self, state: SimulationState, moved: set[int]) -> None:
        groups: dict[Point, list[Drone]] = {}
        for drone in state.active_drones():
            point = self.drone_point(drone)
            if point is not None:
                groups.setdefault(point, []).append(drone)
        for point, drones in groups.items():
            self._draw_group(point, drones, moved)

    def _draw_group(
        self, center: Point, drones: list[Drone], moved: set[int]
    ) -> None:
        """Draw up to ``_MAX_DOTS`` dots in a small grid around a point."""
        shown = drones[:_MAX_DOTS]
        columns = min(len(shown), 4)
        rows = math.ceil(len(shown) / columns)
        step = 9
        left = center[0] - (columns - 1) * step // 2
        top = center[1] - (rows - 1) * step // 2
        for index, drone in enumerate(shown):
            point = (left + index % columns * step,
                     top + index // columns * step)
            color = _DRONE
            if drone.in_transit_connection is not None:
                color = _DRONE_FLYING
            ring = _DRONE_MOVED if drone.drone_id in moved else _OUTLINE
            pygame.draw.circle(self.screen, ring, point, 5)
            pygame.draw.circle(self.screen, color, point, 3)
        if len(drones) > len(shown):
            self._text(
                f"+{len(drones) - len(shown)}",
                (center[0] + columns * step // 2 + 14, center[1]),
                _TEXT,
                True,
            )

    def _draw_status(
        self, state: SimulationState, moves: list[Move], note: str
    ) -> None:
        width, height = self.screen.get_size()
        pygame.draw.rect(
            self.screen, _OUTLINE, pygame.Rect(0, 0, width, _HUD_HEIGHT)
        )
        status = (
            f"Turn {state.turn_number}   moved {len(moves)}   "
            f"delivered {state.delivered_count}/{len(state.drones)}"
            f"   in flight {len(state.drones_in_transit())}"
        )
        self.screen.blit(
            self.big_font.render(status, True, _TEXT), (10, 8)
        )
        controls = f"{_HELP}   delay {self.delay:.2f}s"
        if self.paused:
            controls = "PAUSED   " + controls
        if note:
            controls = f"{note}   {controls}"
        surface = self.font.render(controls, True, _TEXT_DIM)
        self.screen.blit(surface, (width - surface.get_width() - 10, 11))
        move_text = " ".join(
            f"D{m.drone_id}-{m.destination}" for m in moves
        )
        self.screen.blit(
            self.font.render(move_text or "-", True, _TEXT_DIM),
            (10, height - _FOOTER_HEIGHT + 6),
        )

    def _draw_tooltip(
        self, state: SimulationState, name: str, at: Point
    ) -> None:
        """Draw a box with the full details of one zone near the mouse."""
        zone = state.network.zones[name]
        here = [d.drone_id for d in state.drones_at(name)]
        if zone.role is ZoneRole.END:
            count = f"delivered: {state.delivered_count}"
        elif zone.max_drones is None:
            count = f"drones: {len(here)} (no limit)"
        else:
            count = f"drones: {state.occupancy(name)}/{zone.max_drones}"
            if state.reserved(name):
                count += f" (+{state.reserved(name)} arriving)"
        ids = " ".join(f"D{i}" for i in here[:10])
        if len(here) > 10:
            ids += f" +{len(here) - 10}"
        lines = [
            f"{name} [{zone.role.value}, {zone.zone_type.value}]",
            f"color: {zone.color or 'none'}   {count}",
        ]
        if ids:
            lines.append(ids)
        surfaces = [self.font.render(line, True, _TEXT) for line in lines]
        box = pygame.Rect(
            0, 0,
            max(s.get_width() for s in surfaces) + 16,
            sum(s.get_height() for s in surfaces) + 12,
        )
        box.topleft = (at[0] + 14, at[1] + 14)
        box.clamp_ip(self.screen.get_rect())
        pygame.draw.rect(self.screen, _OUTLINE, box)
        pygame.draw.rect(self.screen, _TEXT_DIM, box, 1)
        y = box.top + 6
        for surface in surfaces:
            self.screen.blit(surface, (box.left + 8, y))
            y += surface.get_height()

    def _fit(self, text: str, max_width: int) -> str:
        """Shorten text with a trailing ``~`` until it fits the width."""
        if self.font.size(text)[0] <= max_width:
            return text
        while len(text) > 1 and self.font.size(text + "~")[0] > max_width:
            text = text[:-1]
        return text + "~"

    def _text(
        self, text: str, at: Point, color: RGB, centered: bool = False
    ) -> None:
        surface = self.font.render(text, True, color)
        if centered:
            rect = surface.get_rect(center=at)
            self.screen.blit(surface, rect)
        else:
            self.screen.blit(surface, at)


def _load_color(fraction: float) -> RGB:
    """Return green for a lightly used zone, orange, then red when full."""
    if fraction >= 1.0:
        return 230, 60, 50
    if fraction >= 0.5:
        return 245, 160, 40
    return 70, 200, 90


class GraphicalVisualizer:
    """Renders the network and drone positions in a graphical window.

    The window opens on the first ``begin`` or ``render``. After each
    frame (except the final one when paused or ``hold_final``) it waits
    ``delay`` seconds while handling input: Space pauses
    or resumes, the right arrow steps one turn, up/down (or +/-) change
    the delay, and Esc, q or the window's close button quit. Quitting
    only closes the window: later calls do nothing and the simulation
    carries on to the end, so the turn log is still complete.
    """

    def __init__(
        self,
        delay: float = 0.5,
        size: Point = (1200, 800),
        hold_final: bool = True,
        step: bool = False,
    ) -> None:
        """Store the settings; no window is opened yet.

        Args:
            delay: Seconds each turn stays on screen in auto-play.
            size: Window size in pixels.
            hold_final: After the last turn, keep the window open until
                the user closes it (only if the run completed).
            step: Step mode: start paused and advance one turn per right
                arrow press (Space still switches to auto-play).
        """
        self.delay = delay
        self.size = size
        self.hold_final = hold_final
        self.step = step
        self._window: _Window | None = None
        self._closed = False
        self._finished = False
        self._previous: dict[int, Point] = {}

    @property
    def is_open(self) -> bool:
        """Return whether the window is currently open."""
        return self._window is not None

    def begin(self, state: SimulationState) -> None:
        """Open the window and show the initial state."""
        self._show(state, [])

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Draw the turn, with each move's path highlighted, then wait."""
        self._show(state, moves)

    def close(self) -> None:
        """Close the window, first waiting for the user if requested.

        The view is closed for good afterwards, even if no window was
        ever opened: later ``begin`` / ``render`` calls do nothing.
        """
        window = self._window
        if window is not None and self.hold_final and self._finished:
            window.redraw("finished - press esc to close")
            window.wait_for_quit()
        self._shut()

    def _show(self, state: SimulationState, moves: list[Move]) -> None:
        window = self._open(state.network)
        if window is None:
            return
        trails: list[tuple[Point, Point]] = []
        for move in moves:
            start = self._previous.get(move.drone_id)
            end = self._point_after(window, state, move)
            if start is not None and end is not None and start != end:
                trails.append((start, end))
        window.show(state, moves, trails)
        self._previous = {
            drone.drone_id: point
            for drone in state.drones.values()
            if (point := window.drone_point(drone)) is not None
        }
        self._finished = state.is_complete
        if self._finished and (window.paused or self.hold_final):
            # Nothing comes next: don't ask for a step. With hold_final,
            # close() keeps the final frame up until the user quits.
            return
        if not window.wait():
            self._shut()

    @staticmethod
    def _point_after(
        window: _Window, state: SimulationState, move: Move
    ) -> Point | None:
        """Return where the move ended, delivered drones included."""
        drone = state.drones[move.drone_id]
        if drone.is_delivered and drone.current_zone is not None:
            return window.layout.position(drone.current_zone)
        return window.drone_point(drone)

    def _open(self, network: Network) -> _Window | None:
        if self._closed:
            return None
        if self._window is None:
            self._window = _Window(network, self.size, self.delay)
            self._window.paused = self.step
        return self._window

    def _shut(self) -> None:
        if self._window is not None:
            self.delay = self._window.delay
            self._window.close()
        self._window = None
        self._closed = True
