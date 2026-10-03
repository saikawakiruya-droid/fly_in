"""Tests for droneflow.output.formatter."""

import pytest

from droneflow.output.formatter import TurnLogFormatter
from droneflow.simulation.state import Move


def test_format_turn_joins_moves_with_single_space() -> None:
    """Each move becomes D<ID>-<destination>, separated by one space."""
    moves = [Move(1, "roof1"), Move(2, "corridorA")]
    assert TurnLogFormatter().format_turn(moves) == "D1-roof1 D2-corridorA"


def test_format_turn_single_move_has_no_trailing_space() -> None:
    """A one-move turn has no leading or trailing whitespace."""
    assert TurnLogFormatter().format_turn([Move(2, "goal")]) == "D2-goal"


def test_format_turn_keeps_caller_order() -> None:
    """Moves are not sorted: the caller's order is preserved."""
    moves = [Move(3, "a"), Move(1, "b"), Move(2, "c")]
    assert TurnLogFormatter().format_turn(moves) == "D3-a D1-b D2-c"


def test_format_turn_passes_connection_name_through() -> None:
    """A restricted-transit destination (connection name) is not altered."""
    moves = [Move(1, "a-b")]
    assert TurnLogFormatter().format_turn(moves) == "D1-a-b"


def test_format_turn_empty_returns_empty_string() -> None:
    """An empty move list yields an empty string."""
    assert TurnLogFormatter().format_turn([]) == ""


def test_emit_prints_one_line_per_turn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each non-empty turn is printed on its own line, in order."""
    turns = [[Move(1, "roof1"), Move(2, "corridorA")], [Move(2, "goal")]]
    TurnLogFormatter().emit(turns)
    assert capsys.readouterr().out == "D1-roof1 D2-corridorA\nD2-goal\n"


def test_emit_skips_empty_turns(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Turns where nothing moved produce no output line."""
    turns = [[Move(1, "a")], [], [Move(1, "b")]]
    TurnLogFormatter().emit(turns)
    assert capsys.readouterr().out == "D1-a\nD1-b\n"


def test_emit_no_turns_prints_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No turns at all produces no output."""
    TurnLogFormatter().emit([])
    assert capsys.readouterr().out == ""
