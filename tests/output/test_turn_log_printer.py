"""Tests for droneflow.output.turn_log_printer (TurnLogPrinter).

``FlushCountingIO`` records the text at every ``flush``, so the tests can
check that each turn line is flushed as soon as it is written. Decisions
2026-10-18 "the turn log is written turn by turn by TurnLogPrinter".
"""

import io
from typing import Callable

import pytest

from droneflow.models.network import Network
from droneflow.output.formatter import TurnLogFormatter
from droneflow.output.turn_log_printer import TurnLogPrinter
from droneflow.simulation.state import Move, SimulationState

MakeNetwork = Callable[..., Network]


class FlushCountingIO(io.StringIO):
    """A StringIO that remembers its contents at every flush."""

    def __init__(self) -> None:
        super().__init__()
        self.flushed: list[str] = []

    def flush(self) -> None:
        """Record the text written so far, then flush."""
        self.flushed.append(self.getvalue())
        super().flush()


class StubFormatter(TurnLogFormatter):
    """Returns "X" for every turn and keeps the moves it was given."""

    def __init__(self) -> None:
        self.received: list[list[Move]] = []

    def format_turn(self, moves: list[Move]) -> str:
        """Record the moves and return a fixed line."""
        self.received.append(moves)
        return "X"


@pytest.fixture
def state(make_network: MakeNetwork) -> SimulationState:
    """Return a two-drone state on ``s-a a-b b-g``."""
    return SimulationState(make_network("s-a a-b b-g"), 2)


def test_begin_writes_nothing_and_default_is_stdout(
    state: SimulationState, capsys: pytest.CaptureFixture[str]
) -> None:
    """AP01: begin writes nothing; the default stream is sys.stdout."""
    stream = io.StringIO()
    TurnLogPrinter(stream).begin(state)
    assert stream.getvalue() == ""

    printer = TurnLogPrinter()
    printer.render(state, [Move(1, "a")])

    captured = capsys.readouterr()
    assert captured.out == "D1-a\n"
    assert captured.err == ""


def test_one_line_per_turn_flushed_at_once(state: SimulationState) -> None:
    """AP02: each turn is one line, flushed right after it is written."""
    stream = FlushCountingIO()
    printer = TurnLogPrinter(stream)

    printer.render(state, [Move(1, "a")])
    printer.render(state, [Move(1, "b"), Move(2, "a")])
    printer.render(state, [Move(2, "a-b")])

    assert stream.getvalue() == "D1-a\nD1-b D2-a\nD2-a-b\n"
    assert stream.flushed == [
        "D1-a\n",
        "D1-a\nD1-b D2-a\n",
        "D1-a\nD1-b D2-a\nD2-a-b\n",
    ]


def test_empty_turns_are_not_written(state: SimulationState) -> None:
    """AP03: an empty turn writes no blank line and does not flush."""
    stream = FlushCountingIO()
    printer = TurnLogPrinter(stream)

    printer.render(state, [])
    printer.render(state, [Move(1, "a")])
    printer.render(state, [])
    printer.render(state, [Move(1, "b")])

    assert stream.getvalue() == "D1-a\nD1-b\n"
    assert stream.flushed == ["D1-a\n", "D1-a\nD1-b\n"]


def test_close_flushes_without_closing() -> None:
    """AP04 (1): close flushes once and leaves the stream open."""
    stream = FlushCountingIO()
    printer = TurnLogPrinter(stream)

    printer.close()

    assert stream.flushed == [""]
    assert stream.closed is False
    assert stream.getvalue() == ""


def test_formatting_is_delegated(state: SimulationState) -> None:
    """AP04 (2): the printer's formatter makes the line from the very
    same moves."""
    stream = io.StringIO()
    formatter = StubFormatter()
    moves = [Move(1, "a")]

    printer = TurnLogPrinter(stream)
    printer.formatter = formatter
    printer.render(state, moves)

    assert stream.getvalue() == "X\n"
    assert len(formatter.received) == 1
    assert formatter.received[0] is moves
