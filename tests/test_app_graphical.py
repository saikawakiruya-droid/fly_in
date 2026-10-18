"""Tests for droneflow.app with the graphical view, run headless.

The whole file is skipped when pygame is not installed. ``headless`` sets
``SDL_VIDEODRIVER=dummy``, replaces ``_Window.wait_for_quit`` (the final
wait of ``hold_final=True``) with a spy that returns at once, and arms a
watchdog that posts QUIT after a few seconds, so a run that waits for
good closes its window instead of hanging. Runs use ``delay=0``; no test
sleeps or measures time. A window that cannot be opened is made with a
video driver that does not exist. Decisions 2026-10-18 "visualization in
the CLI phase", "step mode", "the CLI's shape" and "error handling".
"""

import io
import os
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

# importorskip loads pygame before graphical_view does: keep its banner
# off standard output the same way the view does (without overriding).
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
pygame = pytest.importorskip("pygame")

import fly_in  # noqa: E402
from droneflow.app import Application  # noqa: E402
from droneflow.cli import Args  # noqa: E402
from droneflow.errors import VisualizationError  # noqa: E402
from droneflow.visualization import graphical_view  # noqa: E402
from droneflow.visualization.graphical_view import (  # noqa: E402
    GraphicalVisualizer,
)
from droneflow.visualization.terminal_view import (  # noqa: E402
    TerminalVisualizer,
)

WriteMap = Callable[[str], Path]
TtyStream = Callable[..., io.StringIO]

WATCHDOG_MS = 5000
SUMMARY = (
    "summary: 7 turns, 5 drones, 5.00 turns per drone on average, "
    "2.14 moves per turn"
)


@pytest.fixture
def headless(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    """Run on a dummy display; return the calls to ``wait_for_quit``."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    calls: list[object] = []

    def wait_for_quit(self: object) -> None:
        calls.append(self)

    monkeypatch.setattr(graphical_view._Window, "wait_for_quit", wait_for_quit)
    pygame.display.init()
    pygame.event.clear()
    pygame.time.set_timer(pygame.QUIT, WATCHDOG_MS, loops=1)
    yield calls
    pygame.time.set_timer(pygame.QUIT, 0)
    pygame.display.quit()
    pygame.font.quit()


@pytest.fixture
def no_window(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ask SDL for a video driver that does not exist."""
    pygame.display.quit()
    monkeypatch.setenv("SDL_VIDEODRIVER", "nosuch")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    yield
    pygame.display.quit()


@pytest.fixture
def sample_path(write_map: WriteMap, subject_map: str) -> Path:
    """Write the subject's example map and return its path."""
    return write_map(subject_map)


def run_app(args: Args) -> tuple[str, str]:
    """Run the application; return what it wrote to stdout and stderr."""
    out, err = io.StringIO(), io.StringIO()
    Application(args, out, err).run()
    return out.getvalue(), err.getvalue()


@pytest.mark.parametrize("visual", ["graphical", "both"])
def test_stdout_is_the_same_log(
    visual: str,
    sample_path: Path,
    subject_output: list[str],
    headless: list[object],
) -> None:
    """AG01: graphical and both print the same log as none/terminal."""
    out, err = run_app(Args(sample_path, visual, delay=0))

    assert out == "\n".join(subject_output) + "\n"
    assert err.splitlines()[-1] == SUMMARY
    assert "warning:" not in err
    assert len(headless) == 1
    assert ("=== Turn 0 (start)" in err) is (visual == "both")


@pytest.mark.parametrize("case", ["step", "default", "both-step"])
def test_graphical_view_assembly(
    case: str,
    sample_path: Path,
    tty_stream: TtyStream,
    monkeypatch: pytest.MonkeyPatch,
    headless: list[object],
) -> None:
    """AG02: graphical settings; with both only the window steps."""
    monkeypatch.setattr(sys, "stdin", tty_stream())
    args = {
        "step": Args(sample_path, "graphical", delay=0.25, step=True),
        "default": Args(sample_path, "graphical"),
        "both-step": Args(sample_path, "both", step=True),
    }[case]

    views = Application(args, io.StringIO(), io.StringIO())._make_views()

    expected_names = ["terminal", "graphical"]
    if case != "both-step":
        expected_names = ["graphical"]
    assert [v.name for v in views] == expected_names
    graphical = views[-1].view
    assert isinstance(graphical, GraphicalVisualizer)
    assert graphical.hold_final is True
    assert graphical.is_open is False
    if case == "step":
        assert graphical.delay == 0.25
        assert graphical.step is True
    elif case == "default":
        assert graphical.delay == 0.5
        assert graphical.step is False
    else:
        terminal = views[0].view
        assert isinstance(terminal, TerminalVisualizer)
        assert terminal.step is False
        assert graphical.step is True


@pytest.mark.parametrize("visual", ["graphical", "both"])
@pytest.mark.usefixtures("no_window")
def test_window_cannot_open(
    visual: str, sample_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AG03: no window: VisualizationError, other views still closed."""
    closes: list[TerminalVisualizer] = []
    original = TerminalVisualizer.close

    def close(self: TerminalVisualizer) -> None:
        closes.append(self)
        original(self)

    monkeypatch.setattr(TerminalVisualizer, "close", close)
    out, err = io.StringIO(), io.StringIO()

    with pytest.raises(VisualizationError) as info:
        Application(Args(sample_path, visual, delay=0), out, err).run()

    assert str(info.value).startswith("cannot open the graphical window: ")
    assert out.getvalue() == ""
    assert "summary:" not in err.getvalue()
    if visual == "both":
        assert "=== Turn 0 (start)" in err.getvalue()
        assert len(closes) == 1
    else:
        assert closes == []


@pytest.mark.usefixtures("no_window")
def test_main_reports_window_error(
    sample_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AG04: main turns the window error into one line and exit 1."""
    monkeypatch.delenv(fly_in.DEBUG_ENV, raising=False)
    silenced: list[None] = []
    monkeypatch.setattr(
        fly_in, "_silence_stdout", lambda: silenced.append(None)
    )

    code = fly_in.main([str(sample_path), "--visual", "graphical"])

    assert code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("error: cannot open the graphical window: ")
    assert "Traceback" not in captured.err
    assert silenced == []
