"""Tests for the visualizer hooks of SimulationEngine.run (Stage 7).

The engine calls ``begin`` once before the first turn, ``render(state,
moves)`` after every applied turn and ``close`` once at the end, even
when the run stops with an error (decisions 2026-10-17 "Stage 7 API" and
2026-10-18 "begin inside try"). ``call_log`` keeps the calls in order.
"""

from typing import Callable, Protocol

import pytest

from droneflow.errors import SimulationError
from droneflow.models.network import Network
from droneflow.models.world import World
from droneflow.simulation.engine import SimulationEngine
from droneflow.simulation.scheduler import Scheduler
from droneflow.simulation.state import Move, MoveOrder, SimulationState

MakeNetwork = Callable[..., Network]
Script = list[list[MoveOrder]]
Scripted = Callable[[Network, Script], Scheduler]
Follower = Callable[[Network], Scheduler]
Idle = Callable[[Network], Scheduler]
Oscillating = Callable[[Network, str, str], Scheduler]
Call = tuple[object, ...]
Turns = list[list[Move]]


class LoggingView(Protocol):
    """What the ``call_log`` factory returns: a view with its call list."""

    calls: list[Call]

    def begin(self, state: SimulationState) -> None:
        """Log begin."""
        ...

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Log render."""
        ...

    def close(self) -> None:
        """Log close."""
        ...


CallLog = Callable[..., LoggingView]


def names(calls: list[Call]) -> list[object]:
    """Return just the method names of the logged calls."""
    return [call[0] for call in calls]


@pytest.fixture
def two_drone_run(
    make_network: MakeNetwork,
    follower_scheduler: Follower,
    call_log: CallLog,
) -> tuple[list[Call], Turns]:
    """Run 2 drones over ``s-a a-g``; return the log and the turns."""
    network = make_network("s-a a-g")
    view = call_log()
    engine = SimulationEngine(World(network, 2), follower_scheduler(network))
    turns = engine.run(view)
    return view.calls, turns


def test_begin_once_before_the_first_turn(
    two_drone_run: tuple[list[Call], Turns],
) -> None:
    """VH01: begin comes first, once, at turn 0 with all drones at start."""
    calls, _ = two_drone_run

    assert calls[0] == ("begin", 0, 2)
    assert names(calls).count("begin") == 1


def test_render_every_turn_with_its_moves(
    two_drone_run: tuple[list[Call], Turns],
) -> None:
    """VH02: one render per turn, numbered 1, 2, ... with that turn's moves."""
    calls, turns = two_drone_run
    renders = [call for call in calls if call[0] == "render"]

    assert len(renders) == len(turns)
    assert [call[1] for call in renders] == list(range(1, len(turns) + 1))
    for call, moves in zip(renders, turns):
        assert call[2] == moves
        assert moves


def test_close_once_at_the_end(
    two_drone_run: tuple[list[Call], Turns],
) -> None:
    """VH03: the whole sequence is begin, render x n, close."""
    calls, turns = two_drone_run

    assert names(calls) == ["begin", *["render"] * len(turns), "close"]
    assert calls[-1] == ("close",)


@pytest.mark.parametrize("case", ["idle", "turn_limit", "illegal_order"])
def test_close_after_a_simulation_error(
    case: str,
    make_network: MakeNetwork,
    idle_scheduler: Idle,
    oscillating_scheduler: Oscillating,
    scripted_scheduler: Scripted,
    call_log: CallLog,
) -> None:
    """VH04: a SimulationError passes through unchanged, after close."""
    network = make_network("s-a a-g b-g")
    view = call_log()
    max_turns = None
    if case == "idle":
        scheduler = idle_scheduler(network)
        expected = ["begin", "close"]
    elif case == "turn_limit":
        scheduler = oscillating_scheduler(network, "a", "s")
        max_turns = 3
        expected = ["begin", "render", "render", "render", "close"]
    else:
        scheduler = scripted_scheduler(network, [[MoveOrder(1, "b")]])
        expected = ["begin", "close"]
    engine = SimulationEngine(World(network, 1), scheduler, max_turns)

    with pytest.raises(SimulationError):
        engine.run(view)
    assert names(view.calls) == expected


def test_close_after_begin_fails(
    make_network: MakeNetwork,
    follower_scheduler: Follower,
    call_log: CallLog,
) -> None:
    """VH06: a failing begin still closes; no turn is played."""
    network = make_network("s-a a-g")
    view = call_log(fail_on="begin")
    engine = SimulationEngine(World(network, 2), follower_scheduler(network))

    with pytest.raises(RuntimeError, match="^view$"):
        engine.run(view)
    assert names(view.calls) == ["begin", "close"]
    assert engine.state.turn_number == 0


def test_close_after_render_fails(
    make_network: MakeNetwork,
    follower_scheduler: Follower,
    call_log: CallLog,
) -> None:
    """VH05: a failing render propagates as is, after close."""
    network = make_network("s-a a-g")
    view = call_log(fail_on="render")
    engine = SimulationEngine(World(network, 2), follower_scheduler(network))

    with pytest.raises(RuntimeError, match="^view$") as excinfo:
        engine.run(view)
    assert type(excinfo.value) is RuntimeError
    assert names(view.calls) == [
        "begin", "render", "close"
    ]
