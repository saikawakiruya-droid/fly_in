"""Tests for droneflow.app (Application).

``Application(args, out, err)`` writes to two ``StringIO`` objects, so the
turn log (stdout) and everything else (stderr) are compared as text.
Decisions 2026-10-18 "the CLI's shape", "turn log", "error
handling" and 2026-10-17 "terminal view on stderr".
"""

import io
from collections.abc import Callable
from pathlib import Path

import pytest

from droneflow.app import Application
from droneflow.cli import Args, parse_args
from droneflow.errors import (
    FlyInError,
    MapFileError,
    ParseError,
    SimulationError,
    UnreachableGoalError,
)
from droneflow.models.network import Network
from droneflow.output.turn_log_printer import TurnLogPrinter
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.engine import MoveDecider
from droneflow.simulation.scheduling.scheduler import Scheduler
from droneflow.simulation.state import Move, MoveOrder, SimulationState

WriteMap = Callable[[str], Path]
SchedulerMaker = Callable[[Network, Pathfinder], MoveDecider]
StuckAfter = Callable[[int], SchedulerMaker]

LAST_FRAME = "=== Turn 5 | moved 2 | delivered 5/5 ==="
COMMENT_FIRST_MAP = "# c\nnb_drones: 1\n"
UNREACHABLE_MAP = "nb_drones: 1\nstart_hub: s 0 0\nend_hub: g 1 1\n"


def run_app(
    args: Args, out: io.StringIO | None = None
) -> tuple[str, str]:
    """Run the application; return what it wrote to stdout and stderr.

    Exceptions propagate. When the run fails, the text written so far is
    still reachable through the ``out`` passed in.
    """
    out = io.StringIO() if out is None else out
    err = io.StringIO()
    Application(args, out, err).run()
    return out.getvalue(), err.getvalue()


def run_failing(
    args: Args,
    expected: type[BaseException],
    make_scheduler: SchedulerMaker = Scheduler,
) -> tuple[pytest.ExceptionInfo[BaseException], str, str]:
    """Run the application expecting ``expected``; return it and output."""
    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(expected) as info:
        Application(args, out, err, make_scheduler).run()
    return info, out.getvalue(), err.getvalue()


@pytest.fixture
def log(scheduler_output: list[str]) -> str:
    """Return the turn log the real scheduler prints for the example."""
    return "\n".join(scheduler_output) + "\n"


@pytest.fixture
def sample_path(write_map: WriteMap, subject_map: str) -> Path:
    """Write the subject's example map and return its path."""
    return write_map(subject_map)


class RecordingView:
    """Records how many turn lines stdout held at each call."""

    def __init__(self, out: io.StringIO) -> None:
        self.out = out
        self.at_begin: list[int] = []
        self.at_render: list[int] = []
        self.at_close: list[int] = []

    def _lines(self) -> int:
        return self.out.getvalue().count("\n")

    def begin(self, state: SimulationState) -> None:
        """Record the line count."""
        self.at_begin.append(self._lines())

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Record the line count."""
        self.at_render.append(self._lines())

    def close(self) -> None:
        """Record the line count."""
        self.at_close.append(self._lines())


def record_terminal(
    monkeypatch: pytest.MonkeyPatch, out: io.StringIO
) -> RecordingView:
    """Put a RecordingView where the terminal view would be built."""
    view = RecordingView(out)

    def factory(stream: object = None) -> RecordingView:
        return view

    monkeypatch.setattr("droneflow.app.TerminalVisualizer", factory)
    return view


def test_terminal_keeps_stdout_identical(
    sample_path: Path, log: str
) -> None:
    """AA02: the terminal view goes to stderr; stdout is unchanged."""
    out, err = run_app(Args(sample_path))

    assert out == log
    assert err.startswith("=== Turn 0 (start)")
    assert LAST_FRAME in err.splitlines()
    for text in ("===", "\x1b"):
        assert text not in out


def test_log_lines_come_before_each_frame(
    sample_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AA03: each turn line is out before the view draws that turn."""
    out = io.StringIO()
    view = record_terminal(monkeypatch, out)

    run_app(Args(sample_path), out)

    assert view.at_begin == [0]
    assert view.at_render == [1, 2, 3, 4, 5]
    assert view.at_close == [5]


@pytest.mark.parametrize("case", ["missing", "directory", "not-utf8"])
def test_unreadable_map(case: str, tmp_path: Path) -> None:
    """AA06: OS and decoding errors become MapFileError with a cause."""
    if case == "missing":
        path = tmp_path / "missing.txt"
    elif case == "directory":
        path = tmp_path
    else:
        path = tmp_path / "latin1.txt"
        path.write_bytes(b"nb_drones: 1\n\xff\n")

    info, out, err = run_failing(Args(path), MapFileError)

    exc = info.value
    assert isinstance(exc, MapFileError)
    assert isinstance(exc, FlyInError)
    prefix = f"cannot read map file '{path}': "
    assert str(exc).startswith(prefix)
    assert exc.path == str(path)
    assert str(exc) == prefix + exc.reason
    if case == "missing":
        assert exc.reason == "No such file or directory"
    elif case == "not-utf8":
        assert exc.reason == "not UTF-8 text"
    else:
        assert exc.reason != ""
    cause = UnicodeDecodeError if case == "not-utf8" else OSError
    assert isinstance(exc.__cause__, cause)
    assert out == ""
    assert err == ""


@pytest.mark.parametrize(
    ("text", "expected", "message"),
    [
        (
            COMMENT_FIRST_MAP,
            ParseError,
            "line 1: the first line must be 'nb_drones: <n>'",
        ),
        (
            UNREACHABLE_MAP,
            UnreachableGoalError,
            "goal 'g' is unreachable from 's'",
        ),
    ],
    ids=["parse", "unreachable"],
)
def test_map_errors_pass_through(
    text: str,
    expected: type[FlyInError],
    message: str,
    write_map: WriteMap,
) -> None:
    """AA07: parse and reachability errors are raised as they are."""
    info, out, err = run_failing(Args(write_map(text)), expected)

    assert type(info.value) is expected
    assert str(info.value) == message
    assert out == ""
    assert err == ""


def test_failed_run_keeps_the_log_so_far(
    sample_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    log: str,
    stuck_after: StuckAfter,
) -> None:
    """AA13: on a SimulationError the lines so far stay, views close."""
    out, err = io.StringIO(), io.StringIO()
    view = record_terminal(monkeypatch, out)

    with pytest.raises(SimulationError, match="^turn 4: no drone moved"):
        Application(
            Args(sample_path), out, err, make_scheduler=stuck_after(3)
        ).run()

    assert out.getvalue() == "".join(log.splitlines(keepends=True)[:3])
    assert out.getvalue() == (
        "D1-corridorA D2-hub-roof1\n"
        "D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1\n"
        "D1-goal D2-roof2 D3-tunnelB D4-roof1 D5-corridorA\n"
    )
    assert view.at_close == [3]
    assert LAST_FRAME not in err.getvalue()


def test_printer_failures_are_not_guarded(
    sample_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AA14: an error closing the turn log is raised, not a warning."""
    failure = OSError("printer")

    def close(self: TurnLogPrinter) -> None:
        raise failure

    monkeypatch.setattr(TurnLogPrinter, "close", close)

    info, _, err = run_failing(Args(sample_path), OSError)

    assert info.value is failure
    assert LAST_FRAME in err


def test_map_path_shown_as_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AA15 (designed as AA09, part 1): errors show the path as typed."""
    monkeypatch.chdir(tmp_path)
    args = parse_args(["./no_such//map.txt"])

    info, _, _ = run_failing(args, MapFileError)

    assert str(info.value).startswith(
        "cannot read map file './no_such//map.txt': "
    )


# --- byte order mark, injected schedulers -----------------------------


def test_map_with_bom_is_rejected(tmp_path: Path, subject_map: str) -> None:
    """BM04: a map saved with a byte order mark stops at line 1."""
    path = tmp_path / "map.txt"
    path.write_bytes(b"\xef\xbb\xbf" + subject_map.encode())

    info, out, _ = run_failing(Args(path), ParseError)

    assert info.value.args[0] == (
        "line 1: the first line must be 'nb_drones: <n>'"
    )
    assert out == ""


def test_make_scheduler_builds_the_decider(sample_path: Path) -> None:
    """AI01: the application calls ``make_scheduler(network, pathfinder)``
    once and runs the engine with what it returns."""
    made: list[tuple[Network, Pathfinder]] = []

    class Recording:
        """Record how it was built; move D1 on turn 1 only."""

        def __init__(self, network: Network, pathfinder: Pathfinder) -> None:
            """Record the arguments."""
            made.append((network, pathfinder))
            self.turn = 0

        def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
            """Order D1 to corridorA on the first turn, then nothing."""
            self.turn += 1
            return [MoveOrder(1, "corridorA")] if self.turn == 1 else []

    info, out, err = run_failing(
        Args(sample_path), SimulationError, Recording
    )

    assert len(made) == 1
    network, pathfinder = made[0]
    assert pathfinder.network is network
    assert str(info.value) == (
        "turn 2: no drone moved, so the simulation cannot progress"
    )
    assert out == "D1-corridorA\n"


def test_shared_stuck_scheduler(
    sample_path: Path, scheduler_output: list[str], stuck_after: StuckAfter
) -> None:
    """AI02: the conftest's ``stuck_after`` stops a real run part-way."""
    info, out, _ = run_failing(
        Args(sample_path), SimulationError, stuck_after(2)
    )

    assert str(info.value) == (
        "turn 3: D4 is stuck on connection 'hub-roof1': zone 'roof1' is full"
    )
    assert out.splitlines() == scheduler_output[:2]
