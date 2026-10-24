"""Tests for the entry point fly_in.py (main's exception table).

``fly_in.main(argv)`` runs in the test process and ``capsys`` reads what
it wrote. Two cases run ``fly_in.py`` in a real subprocess to check the
exit status and the ``__main__`` wiring.
Decisions 2026-10-18 "error handling", "last resort for unexpected
exceptions" and "the CLI's shape".
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import fly_in
from droneflow.output.turn_log_printer import TurnLogPrinter
from droneflow.simulation.state import Move, SimulationState
from droneflow.visualization.terminal.view import TerminalVisualizer

WriteMap = Callable[[str], Path]

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = (
    "summary: 5 turns, 5 drones, 4.20 turns per drone on average, "
    "3.40 moves per turn"
)
COMMENT_FIRST_MAP = "# c\nnb_drones: 1\n"
UNREACHABLE_MAP = "nb_drones: 1\nstart_hub: s 0 0\nend_hub: g 1 1\n"


def call_main(*argv: str) -> int:
    """Run ``fly_in.main`` with the given arguments."""
    return fly_in.main(list(argv))


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


def test_success(
    sample_path: Path, log: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """AM01: a good run returns 0; stdout is the log, stderr the summary."""
    assert call_main(str(sample_path)) == 0

    captured = capsys.readouterr()
    assert captured.out == log
    assert captured.err.startswith("=== Turn 0 (start)")
    assert captured.err.splitlines()[-1] == SUMMARY


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

    assert call_main(str(path)) == 1

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
        call_main("m.txt", "--visual")

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


@pytest.mark.parametrize("case", ["bug", "other-os-error"])
def test_last_resort(
    case: str,
    sample_path: Path,
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

    assert call_main(str(sample_path)) == 1

    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert len(lines) == 1
    assert lines[0] == expected
    assert "Traceback" not in captured.err
    assert captured.out == ""


def run_script(*argv: str) -> subprocess.CompletedProcess[str]:
    """Run ``fly_in.py`` in a new process from the repository root."""
    return subprocess.run(
        [sys.executable, "fly_in.py", *argv],
        cwd=ROOT,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
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
    result = run_script("no_such_map.txt")

    assert result.returncode == 1
    assert result.stderr == (
        "error: cannot read map file 'no_such_map.txt': "
        "No such file or directory\n"
    )
    assert result.stdout == ""
