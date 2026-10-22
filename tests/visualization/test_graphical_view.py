"""Tests for droneflow.visualization.graphical_view, run headless.

The whole file is skipped when pygame is not installed. ``headless`` sets
``SDL_VIDEODRIVER=dummy`` and initializes the display before the view
opens its window, so events can be posted before a call: the view reads
them while it waits inside ``begin`` / ``render`` / ``close``. No test
sleeps or measures time. A watchdog timer posts QUIT after a few seconds,
so a view that waits for good closes its window and the test fails on
``is_open`` instead of hanging. Decisions 2026-10-17 "window" and
"colors", 2026-10-18 "y up", "step mode" and "points from the Stage 7
test design".
"""

import math
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable

import pytest

# importorskip loads pygame before graphical_view does: keep its banner
# off standard output the same way the view does (without overriding).
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
pygame = pytest.importorskip("pygame")

from droneflow.models.network import Network  # noqa: E402
from droneflow.models.zone import Zone, ZoneType  # noqa: E402
from droneflow.models.world import World  # noqa: E402
from droneflow.pathfinding.pathfinder import Pathfinder  # noqa: E402
from droneflow.simulation.engine import SimulationEngine  # noqa: E402
from droneflow.simulation.scheduling.scheduler import Scheduler  # noqa: E402
from droneflow.simulation.state import Move, SimulationState  # noqa: E402
from droneflow.visualization import graphical_view  # noqa: E402
from droneflow.visualization.graphical_view import (  # noqa: E402
    GraphicalVisualizer,
    _Layout,
    zone_rgb,
)
from droneflow.visualization.geometry import (  # noqa: E402
    distance_to_path,
    middle,
)
from droneflow.visualization.labels import Measure, zone_title  # noqa: E402
from droneflow.visualization.palette import DEFAULT_ZONE_RGB  # noqa: E402

MakeNetwork = Callable[..., Network]
CoordNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]
Snapshot = Callable[[SimulationState], dict[str, object]]
LoadWorld = Callable[[str], World]

ROOT = Path(__file__).resolve().parents[2]
WATCHDOG_MS = 3000


class Headless:
    """Posts input events and re-arms the watchdog."""

    @staticmethod
    def post_key(key: int) -> None:
        """Queue a key press."""
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))

    @staticmethod
    def post_quit() -> None:
        """Queue a click on the window's close button."""
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    @staticmethod
    def post_motion(pos: tuple[int, int]) -> None:
        """Queue a mouse move to a pixel."""
        pygame.event.post(
            pygame.event.Event(
                pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)
            )
        )

    @staticmethod
    def watchdog(ms: int) -> None:
        """Post QUIT once after ``ms`` milliseconds (replaces the last)."""
        pygame.time.set_timer(pygame.QUIT, ms, loops=1)


@pytest.fixture
def headless(monkeypatch: pytest.MonkeyPatch) -> Iterator[Headless]:
    """Initialize a dummy display with an empty queue and a watchdog."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.display.init()
    pygame.event.clear()
    helper = Headless()
    helper.watchdog(WATCHDOG_MS)
    yield helper
    pygame.time.set_timer(pygame.QUIT, 0)
    pygame.display.quit()
    pygame.font.quit()


def run(world: World, view: GraphicalVisualizer) -> list[list[Move]]:
    """Run the real scheduler (Stage 5) over the world with the view."""
    scheduler = Scheduler(world.network, Pathfinder(world.network))
    return SimulationEngine(world, scheduler).run(view)


def plain_run(world: World) -> list[list[Move]]:
    """Run the real scheduler with no view at all."""
    scheduler = Scheduler(world.network, Pathfinder(world.network))
    return SimulationEngine(world, scheduler).run()


@pytest.fixture
def line(make_network: MakeNetwork) -> Network:
    """Return ``s-a a-g``."""
    return make_network("s-a a-g")


def test_nothing_opens_on_construction(headless: Headless) -> None:
    """VG01: building the view opens no window."""
    view = GraphicalVisualizer(delay=0, hold_final=False)

    assert view.is_open is False
    assert pygame.display.get_surface() is None


def test_begin_opens_and_close_closes(
    headless: Headless, line: Network
) -> None:
    """VG02: begin opens the window; close shuts the display down."""
    view = GraphicalVisualizer(delay=0, size=(640, 480), hold_final=False)

    view.begin(SimulationState(line, 1))

    assert view.is_open is True
    assert pygame.display.get_surface().get_size() == (640, 480)
    assert pygame.display.get_caption()[0] == "Fly-in"
    view.close()
    assert view.is_open is False
    assert pygame.display.get_init() is False


def test_layout_y_axis_points_up(coord_network: CoordNetwork) -> None:
    """VG03: x grows right, y grows up, all inside under the status bar."""
    network = coord_network([("s", 0, 0), ("a", 10, 0), ("g", 10, 10)])
    layout = _Layout(network, (1200, 800))
    s, a, g = (layout.position(name) for name in ("s", "a", "g"))

    assert s[1] == a[1]
    assert a[0] > s[0]
    assert g[1] < a[1]
    for x, y in (s, a, g):
        assert 0 <= x < 1200
        assert graphical_view._HUD_HEIGHT < y < 800


@pytest.mark.parametrize("case", ["same_point", "vertical", "flat"])
def test_layout_degenerate_maps(
    case: str, coord_network: CoordNetwork
) -> None:
    """VG04: no division by zero; one axis is never stretched too far.

    Zones at the same point are spread apart (2026-10-22, VO01).
    """
    if case == "same_point":
        network = coord_network([("s", 3, 3), ("a", 3, 3), ("g", 3, 3)])
        layout = _Layout(network, (1200, 800))
        points = {layout.position(name) for name in ("s", "a", "g")}
        assert len(points) == 3
        for p, q in [(p, q) for p in points for q in points if p < q]:
            assert math.dist(p, q) >= 2 * layout.radius
    elif case == "vertical":
        network = coord_network([("s", 0, 0), ("g", 0, 5)])
        layout = _Layout(network, (1200, 800))
        (sx, sy), (gx, gy) = layout.position("s"), layout.position("g")
        assert sx == gx == 600
        assert gy < sy
    else:
        network = coord_network([("s", 0, 0), ("g", 100, 1)])
        layout = _Layout(network, (1200, 800))
        (sx, sy), (gx, gy) = layout.position("s"), layout.position("g")
        assert sy - gy > 0
        assert (sy - gy) * 10 < gx - sx


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("red", (220, 40, 40)),
        ("aquamarine", (127, 255, 212)),
        ("rainbow", DEFAULT_ZONE_RGB),
        ("", DEFAULT_ZONE_RGB),
        (None, DEFAULT_ZONE_RGB),
    ],
)
def test_zone_colors(name: str | None, expected: tuple[int, int, int]) -> None:
    """VG05: palette first, then pygame's names, then the default."""
    assert zone_rgb(name) == expected


@pytest.mark.parametrize("which", ["subject", "restricted_only"])
def test_draws_every_turn_and_closes(
    which: str,
    headless: Headless,
    load_world: LoadWorld,
    subject_map: str,
    restricted_only_map: str,
) -> None:
    """VG06: a whole run draws without error and closes the window."""
    text = subject_map if which == "subject" else restricted_only_map
    view = GraphicalVisualizer(delay=0, hold_final=False)

    turns = run(load_world(text), view)

    assert turns == plain_run(load_world(text))
    assert len(turns) == (5 if which == "subject" else 8)
    assert view.is_open is False
    assert pygame.display.get_init() is False


@pytest.mark.parametrize("event", ["quit", "escape", "q"])
def test_closing_early_keeps_simulating(
    event: str,
    headless: Headless,
    load_world: LoadWorld,
    subject_map: str,
) -> None:
    """VG07: Esc, q or the close button end the view, not the run."""
    if event == "quit":
        headless.post_quit()
    else:
        headless.post_key(pygame.K_ESCAPE if event == "escape" else pygame.K_q)
    view = GraphicalVisualizer(delay=0, hold_final=False)

    turns = run(load_world(subject_map), view)

    assert turns == plain_run(load_world(subject_map))
    assert len(turns) == 5
    assert view.is_open is False


@pytest.mark.parametrize("step", [True, False])
def test_step_mode_starts_paused(
    step: bool, headless: Headless, line: Network
) -> None:
    """VG08: in step mode begin only returns when the watchdog quits."""
    headless.watchdog(200)
    view = GraphicalVisualizer(delay=0, step=step, hold_final=False)

    view.begin(SimulationState(line, 1))

    assert view.is_open is (not step)
    view.close()


def test_right_arrow_steps_one_turn(
    headless: Headless, line: Network, place: Place, snapshot: Snapshot
) -> None:
    """VG09: each right arrow lets exactly one frame go; state untouched."""
    view = GraphicalVisualizer(delay=60, step=True, hold_final=False)
    headless.post_key(pygame.K_RIGHT)
    view.begin(SimulationState(line, 1))
    assert view.is_open is True

    state = place(line, 2, at={1: "a"})
    before = snapshot(state)
    headless.post_key(pygame.K_RIGHT)
    view.render(state, [Move(1, "a")])

    assert view.is_open is True
    assert snapshot(state) == before
    view.close()


def test_space_resumes_auto_play(headless: Headless, line: Network) -> None:
    """VG10: Space leaves the pause, so the zero delay lets begin return."""
    view = GraphicalVisualizer(delay=0, step=True, hold_final=False)
    headless.post_key(pygame.K_SPACE)

    view.begin(SimulationState(line, 1))

    assert view.is_open is True
    view.close()


@pytest.mark.parametrize(
    ("delay", "keys", "expected"),
    [
        (1.0, ["K_UP"], 0.5),
        (1.0, ["K_DOWN"] * 4, 5.0),
        (0.1, ["K_UP"] * 3, 0.05),
    ],
)
def test_delay_keys_and_limits(
    delay: float,
    keys: list[str],
    expected: float,
    headless: Headless,
    line: Network,
) -> None:
    """VG11: up halves, down doubles, within 0.05 and 5 seconds."""
    view = GraphicalVisualizer(delay=delay, step=True)
    for key in keys:
        headless.post_key(getattr(pygame, key))
    headless.post_key(pygame.K_RIGHT)

    view.begin(SimulationState(line, 1))
    view.close()

    assert view.delay == pytest.approx(expected)


@pytest.mark.parametrize("opened", [False, True])
def test_close_twice(opened: bool, headless: Headless, line: Network) -> None:
    """VG12: closing again (or before opening) is harmless."""
    view = GraphicalVisualizer(delay=0, hold_final=False)
    if opened:
        view.begin(SimulationState(line, 1))

    view.close()
    view.close()

    assert view.is_open is False


def test_no_window_after_close(headless: Headless, line: Network) -> None:
    """VG18: once closed, even before opening, begin/render open nothing."""
    view = GraphicalVisualizer(delay=0, hold_final=False)
    view.close()

    view.begin(SimulationState(line, 1))
    assert view.is_open is False
    assert pygame.display.get_surface() is None

    view.render(SimulationState(line, 1), [Move(1, "a")])
    assert view.is_open is False
    assert pygame.display.get_surface() is None


def test_final_frame_held_until_quit(
    headless: Headless, line: Network, place: Place
) -> None:
    """VG13: with hold_final, close waits for Esc after a complete run."""
    view = GraphicalVisualizer(delay=0, hold_final=True)
    view.render(place(line, 1, at={1: "g"}), [Move(1, "g")])
    assert view.is_open is True

    headless.post_key(pygame.K_ESCAPE)
    view.close()

    assert view.is_open is False


@pytest.mark.parametrize("case", ["not_finished", "closed_by_user"])
def test_close_does_not_wait(
    case: str,
    headless: Headless,
    line: Network,
    place: Place,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VG14: no final wait after an unfinished run or a closed window."""
    calls: list[object] = []
    monkeypatch.setattr(
        graphical_view._Window, "wait_for_quit", calls.append
    )
    view = GraphicalVisualizer(delay=0, hold_final=True)
    if case == "not_finished":
        view.render(SimulationState(line, 1), [])
    else:
        headless.post_quit()
        view.begin(SimulationState(line, 1))
        assert view.is_open is False
        view.render(place(line, 1, at={1: "g"}), [Move(1, "g")])

    view.close()

    assert calls == []
    assert view.is_open is False


def test_hover_tooltip(headless: Headless, line: Network) -> None:
    """VG15: moving the mouse onto a zone draws its details (smoke)."""
    view = GraphicalVisualizer(delay=60, step=True)
    headless.post_motion(_Layout(line, view.size).position("a"))
    headless.post_key(pygame.K_RIGHT)

    view.begin(SimulationState(line, 1))

    assert view.is_open is True
    view.close()


def test_import_prints_nothing() -> None:
    """VG16: importing the view writes nothing to standard output."""
    env = {
        key: value for key, value in os.environ.items()
        if key != "PYGAME_HIDE_SUPPORT_PROMPT"
    }
    result = subprocess.run(
        [sys.executable, "-c",
         "import droneflow.visualization.graphical_view"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize("hold_final", [False, True])
def test_step_mode_does_not_wait_on_the_final_frame(
    hold_final: bool, headless: Headless, line: Network, place: Place
) -> None:
    """VG17: the last frame needs no right arrow, even in step mode."""
    headless.watchdog(2000)
    view = GraphicalVisualizer(delay=60, step=True, hold_final=hold_final)

    view.render(place(line, 1, at={1: "g"}), [Move(1, "g")])

    assert view.is_open is True
    if hold_final:
        headless.post_key(pygame.K_ESCAPE)
    view.close()
    assert view.is_open is False


def test_zones_at_one_position_are_all_shown(
    coord_network: CoordNetwork,
) -> None:
    """VO01: zones declared at the same position are drawn apart."""
    network = coord_network([("s", 0, 0), ("a", 3, 0), ("b", 3, 0),
                             ("g", 6, 0)])
    layout = _Layout(network, (1200, 800))

    a, b = layout.position("a"), layout.position("b")

    assert a != b
    assert layout.zone_at(a) == "a"
    assert layout.zone_at(b) == "b"


@pytest.fixture
def through(coord_network: CoordNetwork) -> Callable[..., Network]:
    """Return s, b, c, g on a line, with s-c running over b."""

    def make(types: dict[str, ZoneType] | None = None) -> Network:
        return coord_network(
            [("s", 0, 0), ("b", 3, 0), ("c", 6, 0), ("g", 9, 0)],
            "s-b b-c s-c c-g",
            types=types,
        )

    return make


def test_link_over_a_zone_is_an_arc(
    through: Callable[..., Network],
) -> None:
    """VO02: a connection running over another zone bends round it."""
    network = through()
    layout = _Layout(network, (1200, 800))
    s_c = network.connection_between("s", "c")
    s_b = network.connection_between("s", "b")
    assert s_c is not None and s_b is not None

    path = layout.path(s_c)

    assert len(path) > 2
    assert distance_to_path(layout.position("b"), path) >= (
        layout.radius * 1.2
    )
    assert layout.path(s_b) == [layout.position("s"), layout.position("b")]


def test_drone_in_flight_on_the_arc(
    headless: Headless, through: Callable[..., Network], place: Place
) -> None:
    """VO03: a drone flying to a restricted zone sits mid-arc."""
    network = through({"c": ZoneType.RESTRICTED})
    s_c = network.connection_between("s", "c")
    assert s_c is not None
    state = place(network, 1, flying={1: ("s", "c")})
    view = GraphicalVisualizer(delay=0, hold_final=False)

    view.begin(state)
    window = view._window
    assert window is not None
    point = window.drone_point(state.drones[1])
    view.close()

    assert point == middle(window.layout.path(s_c))


def trails_after(
    view: GraphicalVisualizer,
    before: SimulationState,
    after: SimulationState,
    moves: list[Move],
) -> tuple[list[list[tuple[int, int]]], list[tuple[int, int]]]:
    """Show two frames; return the second one's trails and s-c's path."""
    view.begin(before)
    view.render(after, moves)
    window = view._window
    assert window is not None
    s_c = after.network.connection_between("s", "c")
    assert s_c is not None
    trails, path = list(window._trails), window.layout.path(s_c)
    view.close()
    return trails, path


def test_trail_follows_the_arc(
    headless: Headless, through: Callable[..., Network], place: Place
) -> None:
    """VO04: a move along an arc is traced along the arc."""
    network = through()
    view = GraphicalVisualizer(delay=0, hold_final=False)

    trails, path = trails_after(
        view,
        place(network, 1),
        place(network, 1, at={1: "c"}),
        [Move(1, "c", "s-c")],
    )

    assert trails == [path]


def test_landing_trail_starts_mid_arc(
    headless: Headless, through: Callable[..., Network], place: Place
) -> None:
    """VO05: a landing is traced from the middle of the arc to the zone."""
    network = through({"c": ZoneType.RESTRICTED})
    view = GraphicalVisualizer(delay=0, hold_final=False)

    trails, path = trails_after(
        view,
        place(network, 1, flying={1: ("s", "c")}),
        place(network, 1, at={1: "c"}),
        [Move(1, "c")],
    )

    assert trails == [path[len(path) // 2:]]


def test_self_loop_is_drawn(coord_network: CoordNetwork) -> None:
    """VO06: a self-loop has a loop path above its zone (P06's case)."""
    network = coord_network([("s", 0, 0), ("a", 1, 1), ("g", 2, 2)],
                            "s-a a-a a-g")
    layout = _Layout(network, (1200, 800))
    a_a = network.connection_between("a", "a")
    assert a_a is not None

    path = layout.path(a_a)
    ax, ay = layout.position("a")

    assert len(path) > 3
    assert path[0] == path[-1] == (ax, ay)
    assert middle(path)[1] < ay - layout.radius


@pytest.mark.parametrize(("count", "badges"), [(1, 0), (5, 1)])
def test_drones_at_one_point_are_a_badge(
    count: int,
    badges: int,
    headless: Headless,
    line: Network,
    place: Place,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VO07: one drone is a dot; several at one point are one badge."""
    view = GraphicalVisualizer(delay=0, hold_final=False)
    view.begin(place(line, count))
    window = view._window
    assert window is not None
    rects: list[object] = []
    original = pygame.draw.rect

    def spy(*args: object, **kwargs: object) -> object:
        if kwargs.get("border_radius"):
            rects.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(pygame.draw, "rect", spy)
    window._draw_drones(place(line, count), set())
    view.close()

    assert len(rects) == badges * 2  # the fill and its ring


@pytest.fixture
def opened(
    headless: Headless, load_world: LoadWorld, subject_map: str
) -> Iterator[tuple[GraphicalVisualizer, graphical_view._Window]]:
    """Open the view on the subject's example and hand out its window."""
    world = load_world(subject_map)
    view = GraphicalVisualizer(delay=0, hold_final=False)
    view.begin(SimulationState(world.network, world.nb_drones))
    window = view._window
    assert window is not None
    yield view, window
    view.close()


def event(kind: int, **fields: object) -> Any:
    """Build a pygame event to hand to the window."""
    return pygame.event.Event(kind, **fields)


def test_wheel_zooms(
    opened: tuple[GraphicalVisualizer, graphical_view._Window],
) -> None:
    """VZ01: the wheel zooms in and back out."""
    _, window = opened

    assert window._view_event(event(pygame.MOUSEWHEEL, x=0, y=1))
    assert window.camera.zoom == pytest.approx(1.25)
    assert window._view_event(event(pygame.MOUSEWHEEL, x=0, y=-1))
    assert window.camera.zoom == pytest.approx(1.0)


def test_drag_moves_the_map(
    opened: tuple[GraphicalVisualizer, graphical_view._Window],
) -> None:
    """VZ02: dragging with the left button moves the map, then stops."""
    _, window = opened

    window._view_event(event(pygame.MOUSEBUTTONDOWN, button=1,
                             pos=(100, 100)))
    window._view_event(event(pygame.MOUSEMOTION, pos=(130, 90),
                             rel=(30, -10), buttons=(1, 0, 0)))
    window._view_event(event(pygame.MOUSEBUTTONUP, button=1,
                             pos=(130, 90)))
    window._view_event(event(pygame.MOUSEMOTION, pos=(200, 200),
                             rel=(70, 110), buttons=(0, 0, 0)))

    assert window.camera.offset == (30, -10)


def test_f_fits_the_map(
    opened: tuple[GraphicalVisualizer, graphical_view._Window],
) -> None:
    """VZ03: ``f`` shows the whole map again."""
    _, window = opened
    window.camera.zoom_at((300, 300), 3)
    window.camera.pan(40, 40)

    assert window._view_event(event(pygame.KEYDOWN, key=pygame.K_f))

    assert window.camera.zoom == 1
    assert window.camera.offset == (0, 0)


def test_other_keys_are_left_alone(
    opened: tuple[GraphicalVisualizer, graphical_view._Window],
) -> None:
    """VZ04: Space and the arrows keep their old meaning."""
    _, window = opened

    assert not window._view_event(event(pygame.KEYDOWN, key=pygame.K_SPACE))
    assert not window._view_event(event(pygame.KEYDOWN, key=pygame.K_RIGHT))


def test_detail_levels(
    opened: tuple[GraphicalVisualizer, graphical_view._Window],
    coord_network: CoordNetwork,
    headless: Headless,
) -> None:
    """VZ05: dense maps lose labels, then shrink zones to dots."""
    _, window = opened
    assert window._detail() == (window.layout.radius, True)

    mesh = coord_network(
        [(f"z{x}_{y}", x, y) for x in range(20) for y in range(20)]
    )
    dense = GraphicalVisualizer(delay=0, hold_final=False)
    dense.begin(SimulationState(mesh, 1))
    dense_window = dense._window
    assert dense_window is not None
    radius, labels = dense_window._detail()
    dense_window.camera.zoom_at((600, 400), 0.5)
    small, _ = dense_window._detail()
    dense.close()

    assert labels is False
    assert radius == dense_window.layout.radius
    assert small < radius


def test_hover_after_zooming(
    opened: tuple[GraphicalVisualizer, graphical_view._Window],
) -> None:
    """VZ06: the zone under the mouse is found at any zoom."""
    _, window = opened
    window.camera.zoom_at((600, 400), 2)
    point = window.camera.to_screen(window.layout.position("roof1"))

    window._view_event(event(pygame.MOUSEMOTION, pos=point, rel=(0, 0),
                             buttons=(0, 0, 0)))

    assert window._hover is not None
    assert window._hover[0] == "roof1"


def test_names_get_room_when_zoomed(
    opened: tuple[GraphicalVisualizer, graphical_view._Window],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VZ07: the room for a name follows the zoom."""
    _, window = opened
    widths: list[int] = []

    def spy(zone: Zone, measure: Measure, max_width: int) -> str:
        widths.append(max_width)
        return zone_title(zone, measure, max_width)

    monkeypatch.setattr(graphical_view, "zone_title", spy)
    window.redraw()
    at_one = max(widths)
    widths.clear()
    window.camera.zoom_at((600, 400), 4)
    window.redraw()

    assert max(widths) > at_one


def test_off_screen_is_not_drawn(
    opened: tuple[GraphicalVisualizer, graphical_view._Window],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VZ08: zones and drones off screen are skipped."""
    _, window = opened
    calls: list[object] = []
    original = pygame.draw.aacircle

    def spy(*args: object, **kwargs: object) -> object:
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(pygame.draw, "aacircle", spy)
    window.camera.pan(5000, 0)
    window.redraw()

    assert calls == []
