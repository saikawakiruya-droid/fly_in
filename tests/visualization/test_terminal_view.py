"""Tests for droneflow.visualization.terminal_view (no pygame needed).

Frames are written to a ``StringIO`` and checked as text, with
``color=False`` and an explicit ``width`` unless colors are the point of
the test. A "terminal" is a ``StringIO`` whose ``isatty()`` is True
(``tty_stream``). Decisions 2026-10-17 "terminal view on stderr" and
"colors", 2026-10-18 "step mode".
"""

import io
import re
from typing import Callable

import pytest

from droneflow.models.network import Network
from droneflow.models.world import World
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.engine import SimulationEngine
from droneflow.simulation.scheduler import Scheduler
from droneflow.simulation.state import Move, SimulationState
from droneflow.simulation.observer import TurnObserver
from droneflow.visualization.terminal_view import (
    TerminalVisualizer,
    color_enabled,
)

MakeNetwork = Callable[..., Network]
CoordNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]
Snapshot = Callable[[SimulationState], dict[str, object]]
LoadWorld = Callable[[str], World]
TtyStream = Callable[..., io.StringIO]

ESC = "\x1b"
PROMPT = "-- press Enter for the next turn --"
PAINTED = re.compile(r"\x1b\[38;2;\d+;\d+;\d+m(\w+)")


def run(world: World, view: TurnObserver) -> list[list[Move]]:
    """Run the real scheduler (Stage 5) over the world with the view."""
    scheduler = Scheduler(world.network, Pathfinder(world.network))
    return SimulationEngine(world, scheduler).run(view)


def headers_and_prompts(text: str) -> list[str]:
    """Return the frame headers and step prompts, in output order."""
    return [
        line for line in text.splitlines()
        if line.startswith("===") or line == PROMPT
    ]


class FlushCountingIO(io.StringIO):
    """A StringIO counting its flush calls."""

    def __init__(self) -> None:
        super().__init__()
        self.flushes = 0

    def flush(self) -> None:
        """Count, then flush."""
        self.flushes += 1
        super().flush()


@pytest.fixture
def colored(coord_network: CoordNetwork) -> Network:
    """Return ``s - r - g`` in a row, with r painted red."""
    return coord_network(
        [("s", 0, 0), ("r", 5, 0), ("g", 10, 0)],
        "s-r r-g",
        colors={"r": "red"},
    )


def test_default_stream_is_stderr(
    make_network: MakeNetwork, capsys: pytest.CaptureFixture[str]
) -> None:
    """VT01: built under capsys, the view writes to stderr only."""
    view = TerminalVisualizer()
    state = SimulationState(make_network("s-a a-g"), 1)

    view.begin(state)
    view.render(state, [])
    view.close()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "=== Turn 0 (start)" in captured.err


def test_begin_shows_the_initial_state(make_network: MakeNetwork) -> None:
    """VT02: header, legend, zone grid and drones of turn 0."""
    out = io.StringIO()
    view = TerminalVisualizer(out, color=False, width=100)

    view.begin(SimulationState(make_network("s-a a-g"), 2))

    text = out.getvalue()
    lines = text.splitlines()
    assert lines[0] == (
        "=== Turn 0 (start) | 2 drones | 3 zones, 2 connections ==="
    )
    assert lines[1].startswith("key: S=start E=end ")
    assert "s S 2/-" in text
    assert "a . 0/1" in text
    assert "drones: s[D1 D2]" in lines
    assert "in flight:" not in text


def test_frame_returns_the_lines_render_writes(
    make_network: MakeNetwork, place: Place
) -> None:
    """VT03: frame builds the lines without writing; render writes them."""
    state = place(make_network("s-a a-g"), 2, at={1: "a"})
    moves = [Move(1, "a")]
    out = io.StringIO()
    view = TerminalVisualizer(out, color=False, width=100)

    lines = view.frame(state, moves)

    assert out.getvalue() == ""
    assert lines[0] == "=== Turn 0 | moved 1 | delivered 0/2 ==="
    assert lines[1] == "moves: D1-a"
    assert any("a . 1/1*" in line for line in lines)
    assert any(
        line.startswith("drones:") and "a[D1]" in line for line in lines
    )

    view.render(state, moves)
    assert out.getvalue() == "\n".join(lines) + "\n"


def test_restricted_blocked_and_end_zones(
    load_world: LoadWorld, restricted_only_map: str
) -> None:
    """VT04: connection name, reservation, blocked and end counts."""
    out = io.StringIO()
    run(load_world(restricted_only_map),
        TerminalVisualizer(out, color=False, width=100))
    frames = out.getvalue().split("=== Turn ")[1:]

    first_turn = frames[1]
    assert first_turn.startswith("1 |")
    assert "moves: D1-hub-roof1" in first_turn
    assert "roof1     R 0/1+1*" in first_turn
    assert "corridorA X --" in first_turn
    assert "in flight: D1 hub-roof1 -> roof1" in first_turn
    assert "goal      E 5/-" in frames[-1]


def test_drone_ids_are_grouped(
    make_network: MakeNetwork, place: Place
) -> None:
    """VT05: three or more consecutive ids become a range."""
    network = make_network("s-a a-g", capacity={"a": 2})
    out = io.StringIO()

    TerminalVisualizer(out, color=False, width=100).begin(
        place(network, 7, at={4: "a", 6: "a"})
    )

    assert "drones: s[D1..D3 D5 D7] a[D4 D6]" in out.getvalue().splitlines()


def test_wrapping_and_long_names(
    make_network: MakeNetwork, place: Place
) -> None:
    """VT06: lines fit the width; long names are cut only in the grid."""
    long_name = "abcdefghijklmnopqrst"
    network = make_network(f"s-a a-{long_name} {long_name}-g")
    state = place(network, 8, at={1: long_name})
    moves = [Move(i, "a") for i in range(1, 9)]

    lines = TerminalVisualizer(io.StringIO(), color=False, width=40).frame(
        state, moves
    )

    text = "\n".join(lines)
    assert f"  {long_name[:17]}~ ." in text
    assert f"{long_name}[D1]" in text
    first = next(
        i for i, line in enumerate(lines) if line.startswith("moves:")
    )
    assert lines[first + 1].startswith(" " * len("moves: ") + "D")
    assert all(len(line) <= 40 for line in lines[1:])


def test_color_forced_off(colored: Network) -> None:
    """VT07: color=False writes no escape code at all."""
    out = io.StringIO()
    view = TerminalVisualizer(out, color=False)

    view.begin(SimulationState(colored, 1))
    view.render(SimulationState(colored, 1), [Move(1, "r")])

    assert ESC not in out.getvalue()


def test_color_forced_on(colored: Network) -> None:
    """VT08: zone names in 24-bit palette colors; bold headers."""
    out = io.StringIO()
    view = TerminalVisualizer(out, color=True, width=100)

    view.begin(SimulationState(colored, 1))
    view.render(SimulationState(colored, 1), [Move(1, "r")])

    text = out.getvalue()
    assert f"{ESC}[38;2;220;40;40mr{ESC}[0m" in text
    assert text.startswith(f"{ESC}[1m=== Turn 0 (start)")
    assert f"{ESC}[1m=== Turn 0 |" in text


@pytest.mark.parametrize(
    ("tty", "no_color", "expected"),
    [
        (False, None, False),
        (True, None, True),
        (True, "1", False),
        (True, "", True),
    ],
)
def test_color_auto_detection(
    tty: bool,
    no_color: str | None,
    expected: bool,
    colored: Network,
    tty_stream: TtyStream,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VT09: colors only on a terminal, and NO_COLOR only when non-empty."""
    if no_color is None:
        monkeypatch.delenv("NO_COLOR", raising=False)
    else:
        monkeypatch.setenv("NO_COLOR", no_color)
    out = tty_stream() if tty else io.StringIO()

    view = TerminalVisualizer(out)

    assert color_enabled(out) is expected
    assert view.color is expected
    view.begin(SimulationState(colored, 1))
    assert (ESC in out.getvalue()) is expected


def test_unknown_and_missing_colors_stay_plain(
    coord_network: CoordNetwork,
) -> None:
    """VT10: rainbow and no color are not painted; known ones are."""
    network = coord_network(
        [("s", 0, 0), ("u", 1, 0), ("n", 2, 0), ("b", 3, 0), ("g", 4, 0)],
        "s-u u-n n-b b-g",
        colors={"u": "rainbow", "b": "blue"},
    )
    out = io.StringIO()
    view = TerminalVisualizer(out, color=True, width=100)

    view.begin(SimulationState(network, 1))
    view.render(SimulationState(network, 1), [Move(1, "u"), Move(1, "n")])

    assert set(PAINTED.findall(out.getvalue())) == {"b"}


def test_close_flushes_without_closing() -> None:
    """VT11: close flushes the stream and leaves it usable."""
    out = FlushCountingIO()

    TerminalVisualizer(out, color=False).close()

    assert out.flushes == 1
    assert out.closed is False
    out.write("still open")


def test_step_mode_waits_for_enter(
    make_network: MakeNetwork,
    tty_stream: TtyStream,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """VT12: one Enter after each frame but the last, prompt on the view."""
    out = io.StringIO()
    inp = tty_stream("\n" * 5)
    view = TerminalVisualizer(out, color=False, step=True, input_stream=inp)

    turns = run(World(make_network("s-a a-g"), 2), view)

    assert len(turns) == 3
    order = headers_and_prompts(out.getvalue())
    assert [line == PROMPT for line in order] == [
        False, True, False, True, False, True, False
    ]
    assert inp.read() == "\n\n"
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("case", ["input_not_a_terminal", "step_off"])
def test_no_wait_without_a_terminal_or_step(
    case: str, make_network: MakeNetwork, tty_stream: TtyStream
) -> None:
    """VT13: piped input or step=False never prompts nor reads."""
    out = io.StringIO()
    if case == "input_not_a_terminal":
        inp = io.StringIO("\n" * 5)
        step = True
    else:
        inp = tty_stream("\n" * 5)
        step = False
    view = TerminalVisualizer(out, color=False, step=step, input_stream=inp)

    assert view.step is False
    turns = run(World(make_network("s-a a-g"), 2), view)

    assert len(turns) == 3
    assert PROMPT not in out.getvalue()
    assert inp.tell() == 0


def test_end_of_input_stops_stepping(
    make_network: MakeNetwork, tty_stream: TtyStream
) -> None:
    """VT14: at EOF the view prompts once, then runs through."""
    out = io.StringIO()
    view = TerminalVisualizer(
        out, color=False, step=True, input_stream=tty_stream("")
    )

    run(World(make_network("s-a a-g"), 2), view)

    order = headers_and_prompts(out.getvalue())
    assert order.count(PROMPT) == 1
    assert order[1] == PROMPT
    assert len(order) == 5
    assert view.step is False


def test_views_only_read_the_state(
    make_network: MakeNetwork, place: Place, snapshot: Snapshot
) -> None:
    """VT15: begin, render and frame leave the state unchanged."""
    state = place(make_network("s-a a-g"), 2, at={1: "a"})
    before = snapshot(state)
    view = TerminalVisualizer(io.StringIO(), color=True, width=100)

    view.begin(state)
    view.render(state, [Move(1, "a")])
    view.frame(state, [Move(1, "a")])

    assert snapshot(state) == before


def test_subject_map_end_to_end(
    load_world: LoadWorld,
    subject_map: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """VT16: one frame per turn plus turn 0, and nothing on stdout."""
    out = io.StringIO()

    turns = run(load_world(subject_map),
                TerminalVisualizer(out, color=False, width=100))

    headers = [
        line for line in out.getvalue().splitlines()
        if line.startswith("=== Turn")
    ]
    assert len(turns) == 5
    assert len(headers) == len(turns) + 1
    assert headers[-1] == "=== Turn 5 | moved 2 | delivered 5/5 ==="
    assert capsys.readouterr().out == ""
