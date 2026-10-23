"""Tests for the entry point fly_in.py (main's exception table).

``fly_in.main(argv)`` runs in the test process and ``capsys`` reads what
it wrote. ``fly_in._silence_stdout`` is always replaced by a spy (the
real one points the process's stdout at devnull) and ``FLYIN_DEBUG`` is
cleared unless a test sets it. Two cases run ``fly_in.py`` in a real
subprocess to check the exit status and the ``__main__`` wiring.
Decisions 2026-10-18 "error handling", "close failures are a warning",
"last resort for unexpected exceptions" and "the CLI's shape".
"""

import errno
import functools
import io
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import fly_in
from droneflow.app import Application
from droneflow.errors import ParseError
from droneflow.models.network import Network
from droneflow.output.turn_log_printer import TurnLogPrinter
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.engine import MoveDecider
from droneflow.simulation.state import Move, SimulationState
from droneflow.visualization.terminal_view import TerminalVisualizer

WriteMap = Callable[[str], Path]
StuckAfter = Callable[[int], Callable[[Network, Pathfinder], MoveDecider]]

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = (
    "summary: 5 turns, 5 drones, 4.20 turns per drone on average, "
    "3.40 moves per turn"
)
COMMENT_FIRST_MAP = "# c\nnb_drones: 1\n"
UNREACHABLE_MAP = "nb_drones: 1\nstart_hub: s 0 0\nend_hub: g 1 1\n"
CLOSE_WARNING = "warning: could not close the terminal view: boom"


def call_main(*argv: str) -> int:
    """Run ``fly_in.main`` with the given arguments."""
    return fly_in.main(list(argv))


@pytest.fixture(autouse=True)
def no_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test without FLYIN_DEBUG, whatever the shell has."""
    monkeypatch.delenv(fly_in.DEBUG_ENV, raising=False)


@pytest.fixture(autouse=True)
def silenced(monkeypatch: pytest.MonkeyPatch) -> list[None]:
    """Replace ``_silence_stdout`` with a spy; return its calls."""
    calls: list[None] = []
    monkeypatch.setattr(
        fly_in, "_silence_stdout", lambda: calls.append(None)
    )
    return calls


@pytest.fixture
def log(scheduler_output: list[str]) -> str:
    """Return the turn log the real scheduler prints for the example."""
    return "\n".join(scheduler_output) + "\n"


@pytest.fixture
def sample_path(write_map: WriteMap, subject_map: str) -> Path:
    """Write the subject's example map and return its path."""
    return write_map(subject_map)


def raising_app(
    monkeypatch: pytest.MonkeyPatch, exc: BaseException
) -> None:
    """Replace fly_in.Application with one whose ``run`` raises ``exc``."""

    class RaisingApp:
        def __init__(self, args: object) -> None:
            self.args = args

        def run(self) -> None:
            raise exc

    monkeypatch.setattr(fly_in, "Application", RaisingApp)


@pytest.fixture
def fail_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make TerminalVisualizer.close flush as usual, then fail."""
    original = TerminalVisualizer.close

    def close(self: TerminalVisualizer) -> None:
        original(self)
        raise RuntimeError("boom")

    monkeypatch.setattr(TerminalVisualizer, "close", close)


def test_success(
    sample_path: Path, log: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """AM01: a good run returns 0; stdout is the log, stderr the summary."""
    assert call_main(str(sample_path), "--visual", "none") == 0

    captured = capsys.readouterr()
    assert captured.out == log
    assert captured.err == SUMMARY + "\n"


@pytest.mark.parametrize("case", ["missing", "parse", "unreachable"])
def test_fly_in_errors(
    case: str,
    write_map: WriteMap,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AM02: a FlyInError is one ``error:`` line and exit status 1."""
    if case == "missing":
        path = tmp_path / "no_such.txt"
        expected = (
            f"error: cannot read map file '{path}': "
            "No such file or directory"
        )
    elif case == "parse":
        path = write_map(COMMENT_FIRST_MAP)
        expected = "error: line 1: the first line must be 'nb_drones: <n>'"
    else:
        path = write_map(UNREACHABLE_MAP)
        expected = "error: goal 'g' is unreachable from 's'"

    assert call_main(str(path), "--visual", "none") == 1

    captured = capsys.readouterr()
    assert captured.err == expected + "\n"
    assert captured.out == ""


def test_bad_arguments_exit_2_before_anything(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AM03: invalid arguments exit 2 and no Application is built."""

    class NeverBuilt:
        def __init__(self, args: object) -> None:
            raise AssertionError("Application must not be built")

    monkeypatch.setattr(fly_in, "Application", NeverBuilt)

    with pytest.raises(SystemExit) as info:
        call_main("m.txt", "--visual", "graphical")

    assert info.value.code == 2
    assert "usage:" in capsys.readouterr().err


def test_interrupt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AM04: Ctrl+C is ``error: interrupted`` and exit status 130."""
    raising_app(monkeypatch, KeyboardInterrupt())

    assert call_main("m.txt") == fly_in.EXIT_INTERRUPTED == 130

    captured = capsys.readouterr()
    assert captured.err == "error: interrupted\n"
    assert captured.out == ""


def test_interrupt_during_the_run(
    sample_path: Path,
    log: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AM05: Ctrl+C in turn 3: the log so far stays, views close."""
    original_render = TurnLogPrinter.render
    renders: list[int] = []

    def render(
        self: TurnLogPrinter, state: SimulationState, moves: list[Move]
    ) -> None:
        renders.append(len(moves))
        if len(renders) == 3:
            raise KeyboardInterrupt
        original_render(self, state, moves)

    original_close = TerminalVisualizer.close
    closes: list[TerminalVisualizer] = []

    def close(self: TerminalVisualizer) -> None:
        closes.append(self)
        original_close(self)

    monkeypatch.setattr(TurnLogPrinter, "render", render)
    monkeypatch.setattr(TerminalVisualizer, "close", close)

    assert call_main(str(sample_path)) == 130

    captured = capsys.readouterr()
    assert captured.out == "".join(log.splitlines(keepends=True)[:2])
    assert captured.err.splitlines()[-1] == "error: interrupted"
    assert "summary:" not in captured.err
    assert len(closes) == 1


class BrokenStdout(io.StringIO):
    """A stdout whose reader went away."""

    def write(self, text: str) -> int:
        """Fail like a closed pipe."""
        raise BrokenPipeError(errno.EPIPE, "Broken pipe")


@pytest.mark.parametrize(
    "case",
    ["broken-pipe", "real-path"],
)
def test_closed_pipe(
    case: str,
    sample_path: Path,
    silenced: list[None],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AM06: a closed stdout pipe: nothing printed, exit status 1."""
    if case == "broken-pipe":
        raising_app(monkeypatch, BrokenPipeError())
    else:
        monkeypatch.setattr(sys, "stdout", BrokenStdout())

    assert call_main(str(sample_path), "--visual", "none") == 1

    assert capsys.readouterr().err == ""
    assert silenced == [None]


@pytest.mark.parametrize("case", ["bug", "other-os-error"])
def test_last_resort(
    case: str,
    sample_path: Path,
    silenced: list[None],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AM08: unexpected exceptions become one internal error line."""
    if case == "bug":
        raising_app(monkeypatch, ValueError("injected bug"))
        expected = "error: internal error: ValueError: injected bug"
    else:
        raising_app(monkeypatch, PermissionError("denied"))
        expected = "error: internal error: PermissionError: denied"

    assert call_main(str(sample_path), "--visual", "none") == 1

    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert len(lines) == 1
    assert lines[0] == expected
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert silenced == []


def test_debug_lets_bugs_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """AM09 (1): FLYIN_DEBUG=1 lets the very same exception propagate."""
    bug = ValueError("x")
    raising_app(monkeypatch, bug)
    monkeypatch.setenv(fly_in.DEBUG_ENV, "1")

    with pytest.raises(ValueError) as info:
        call_main("m.txt")

    assert info.value is bug


@pytest.mark.parametrize("value", ["0", "true", ""])
def test_debug_needs_exactly_1(
    value: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AM09 (2): any other FLYIN_DEBUG value keeps the last resort."""
    raising_app(monkeypatch, ValueError("x"))
    monkeypatch.setenv(fly_in.DEBUG_ENV, value)

    assert call_main("m.txt") == 1

    assert capsys.readouterr().err == "error: internal error: ValueError: x\n"


@pytest.mark.parametrize(
    ("exc", "code", "message"),
    [
        (ParseError(1, "bad"), 1, "error: line 1: bad\n"),
        (KeyboardInterrupt(), 130, "error: interrupted\n"),
    ],
    ids=["fly-in-error", "interrupt"],
)
def test_debug_keeps_known_errors(
    exc: BaseException,
    code: int,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AM09 (3): FLYIN_DEBUG=1 does not change the known cases."""
    raising_app(monkeypatch, exc)
    monkeypatch.setenv(fly_in.DEBUG_ENV, "1")

    assert call_main("m.txt") == code

    assert capsys.readouterr().err == message


@pytest.mark.usefixtures("fail_close")
def test_close_failure_after_success(
    sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AM10 (1): a failing close does not turn success into failure."""
    assert call_main(str(sample_path)) == 0

    assert capsys.readouterr().err.splitlines()[-2:] == [
        CLOSE_WARNING,
        SUMMARY,
    ]


@pytest.mark.usefixtures("fail_close")
def test_close_failure_after_failure(
    sample_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stuck_after: StuckAfter,
) -> None:
    """AM10 (2): the warning comes first, then the run's own error."""
    monkeypatch.setattr(
        fly_in,
        "Application",
        functools.partial(Application, make_scheduler=stuck_after(0)),
    )

    assert call_main(str(sample_path)) == 1

    assert capsys.readouterr().err.splitlines()[-2:] == [
        CLOSE_WARNING,
        "error: turn 1: no drone moved, so the simulation cannot progress",
    ]


def run_script(*argv: str) -> subprocess.CompletedProcess[str]:
    """Run ``fly_in.py`` in a new process from the repository root."""
    env = {k: v for k, v in os.environ.items() if k != fly_in.DEBUG_ENV}
    return subprocess.run(
        [sys.executable, "fly_in.py", *argv],
        cwd=ROOT,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        env=env,
        timeout=60,
    )


def test_script_success(scheduler_output: list[str]) -> None:
    """AE01: the default map runs in a real process and exits 0."""
    result = run_script("maps/subject_example.txt")

    assert result.returncode == 0
    assert result.stdout.splitlines() == scheduler_output
    assert result.stderr.splitlines()[-1] == SUMMARY
    assert "Traceback" not in result.stderr
    assert "===" not in result.stdout


def test_script_error() -> None:
    """AE02: a missing map is one line on stderr and exit status 1."""
    result = run_script("no_such_map.txt", "--visual", "none")

    assert result.returncode == 1
    assert result.stderr == (
        "error: cannot read map file 'no_such_map.txt': "
        "No such file or directory\n"
    )
    assert result.stdout == ""


def test_parse_only_unwritable(
    sample_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SM01: a --parse-only file that cannot be written exits with 1."""
    path = str(tmp_path / "no_dir" / "w.json")

    assert call_main(str(sample_path), "--parse-only", path) == 1

    captured = capsys.readouterr()
    assert captured.err == (
        f"error: cannot write '{path}': No such file or directory\n"
    )
    assert captured.out == ""


def test_from_world_not_json(
    sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SM02: a map given as a world file is one error line, exit 1."""
    path = str(sample_path)

    assert call_main(path, "--from-world", "--visual", "none") == 1

    assert capsys.readouterr().err == (
        f"error: invalid world file '{path}': "
        "not JSON: Expecting value (line 1)\n"
    )


def test_parser_then_simulation(
    sample_path: Path,
    tmp_path: Path,
    log: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SM03: map -> world file -> simulation, through main both times."""
    world = str(tmp_path / "w.json")

    assert call_main(str(sample_path), "--parse-only", world) == 0
    capsys.readouterr()
    assert call_main(world, "--from-world", "--visual", "none") == 0

    assert capsys.readouterr().out == log
