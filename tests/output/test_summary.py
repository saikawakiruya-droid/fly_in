"""Tests for droneflow.output.summary (RunSummary).

Decisions 2026-10-18 "print the total turns and two secondary metrics to
stderr at the end of a run".
"""

import pytest

from droneflow.output.summary import RunSummary
from droneflow.simulation.state import Move

SUBJECT_SUMMARY = (
    "summary: 7 turns, 5 drones, 5.00 turns per drone on average, "
    "2.14 moves per turn"
)


def parse_line(line: str) -> list[Move]:
    """Turn ``"D1-a D2-b-c"`` back into the moves it was printed from."""
    moves = []
    for token in line.split():
        drone, destination = token[1:].split("-", 1)
        moves.append(Move(int(drone), destination))
    return moves


def test_subject_example(subject_output: list[str]) -> None:
    """AS01: the subject's example gives 7 turns, 5.00 and 2.14."""
    turns = [parse_line(line) for line in subject_output]

    summary = RunSummary.from_turns(turns, 5)

    assert summary == RunSummary(
        total_turns=7,
        nb_drones=5,
        average_turns_per_drone=5.0,
        moves_per_turn=15 / 7,
    )
    assert summary.describe() == SUBJECT_SUMMARY


def test_delivery_turn_is_the_last_appearance() -> None:
    """AS02: a drone counts as delivered on the turn it last moved.

    Connection names (restricted transit) are moves like any other.
    """
    turns = [
        [Move(1, "s-r")],
        [Move(1, "r"), Move(2, "a")],
        [Move(1, "g"), Move(2, "g")],
    ]

    summary = RunSummary.from_turns(turns, 2)

    assert summary.total_turns == 3
    assert summary.average_turns_per_drone == 3.0
    assert summary.moves_per_turn == pytest.approx(5 / 3)
    assert "3.00 turns per drone" in summary.describe()
    assert "1.67 moves per turn" in summary.describe()


def test_empty_run() -> None:
    """AS03: no turns and no drones divide by nothing."""
    empty = RunSummary.from_turns([], 0)
    assert empty == RunSummary(0, 0, 0.0, 0.0)
    assert empty.describe() == (
        "summary: 0 turns, 0 drones, 0.00 turns per drone on average, "
        "0.00 moves per turn"
    )

    idle = RunSummary.from_turns([], 3)
    assert idle.total_turns == 0
    assert idle.average_turns_per_drone == 0.0
    assert idle.describe().startswith(
        "summary: 0 turns, 3 drones, 0.00 turns per drone"
    )
