"""Tests for droneflow.simulation.engine (SimulationEngine)."""

from pathlib import Path
from typing import Callable

import pytest

from droneflow.errors import SimulationError
from droneflow.models.network import Network
from droneflow.models.world import World
from droneflow.models.zone import ZoneType
from droneflow.output.formatter import TurnLogFormatter
from droneflow.parsing.map_parser import MapParser
from droneflow.simulation.engine import SimulationEngine, default_turn_limit
from droneflow.simulation.scheduler import Scheduler
from droneflow.simulation.state import MoveOrder
from droneflow.visualization.base import Visualizer

MakeNetwork = Callable[..., Network]
WriteMap = Callable[[str], Path]
Script = list[list[MoveOrder]]
Scripted = Callable[[Network, Script], Scheduler]
Follower = Callable[[Network], Scheduler]
Idle = Callable[[Network], Scheduler]
Oscillating = Callable[[Network, str, str], Scheduler]
Recorder = tuple[Visualizer, list[tuple[int, int, bool]]]

R = ZoneType.RESTRICTED


def script_from_output(lines: list[str]) -> Script:
    """Turn ``D<n>-<zone>`` lines into one order per move (no restricted)."""
    script: Script = []
    for line in lines:
        turn: list[MoveOrder] = []
        for token in line.split():
            drone, zone = token.split("-", 1)
            turn.append(MoveOrder(int(drone[1:]), zone))
        script.append(turn)
    return script


def test_runs_to_completion(
    make_network: MakeNetwork, follower_scheduler: Follower
) -> None:
    """G01: every turn has moves, in drone_id order, until all deliver."""
    network = make_network("s-a a-b b-g")
    engine = SimulationEngine(World(network, 3), follower_scheduler(network))
    turns = engine.run()

    assert len(turns) == 5
    for moves in turns:
        assert moves
        ids = [move.drone_id for move in moves]
        assert ids == sorted(ids)
    assert engine.state.is_complete is True


def test_render_once_per_turn(
    make_network: MakeNetwork,
    follower_scheduler: Follower,
    recorder: Recorder,
) -> None:
    """G02: render follows every applied turn; the visualizer is optional."""
    network = make_network("s-a a-b b-g")
    visualizer, records = recorder
    turns = SimulationEngine(
        World(network, 3), follower_scheduler(network)
    ).run(visualizer)

    assert len(records) == len(turns)
    assert [turn for turn, _, _ in records] == list(
        range(1, len(turns) + 1)
    )
    assert [done for _, _, done in records] == (
        [False] * (len(turns) - 1) + [True]
    )

    again = make_network("s-a a-b b-g")
    assert SimulationEngine(
        World(again, 3), follower_scheduler(again)
    ).run() == turns


def test_turn_without_movement_is_an_error(
    make_network: MakeNetwork, idle_scheduler: Idle, recorder: Recorder
) -> None:
    """G03: a turn where nothing moves stops the simulation."""
    network = make_network("s-a a-g")
    engine = SimulationEngine(World(network, 1), idle_scheduler(network))
    visualizer, records = recorder

    with pytest.raises(SimulationError, match="no drone moved"):
        engine.run(visualizer)
    assert records == []
    assert engine.state.turn_number == 1


def test_landing_alone_counts_as_progress(
    make_network: MakeNetwork, scripted_scheduler: Scripted
) -> None:
    """G04: a turn with only an automatic landing is not 'no movement'."""
    network = make_network("s-r r-g", types={"r": R})
    script = [[MoveOrder(1, "r")], [], [MoveOrder(1, "g")]]
    engine = SimulationEngine(
        World(network, 1), scripted_scheduler(network, script)
    )
    formatter = TurnLogFormatter()

    turns = engine.run()

    assert [formatter.format_turn(m) for m in turns] == [
        "D1-s-r", "D1-r", "D1-g"
    ]


def test_turn_limit_stops_oscillation(
    make_network: MakeNetwork,
    oscillating_scheduler: Oscillating,
    recorder: Recorder,
) -> None:
    """G05: moving forever without finishing hits max_turns."""
    network = make_network("s-a a-g")
    engine = SimulationEngine(
        World(network, 1),
        oscillating_scheduler(network, "a", "s"),
        max_turns=5,
    )
    visualizer, records = recorder

    with pytest.raises(SimulationError) as excinfo:
        engine.run(visualizer)
    assert "not finished after 5 turns" in str(excinfo.value)
    assert "0/1" in str(excinfo.value)
    assert len(records) == 5


@pytest.mark.parametrize(("max_turns", "finishes"), [(2, True), (1, False)])
def test_turn_limit_boundary(
    make_network: MakeNetwork,
    scripted_scheduler: Scripted,
    max_turns: int,
    finishes: bool,
) -> None:
    """G06: finishing exactly on the limit is fine; one turn less is not."""
    network = make_network("s-a a-g")
    script = [[MoveOrder(1, "a")], [MoveOrder(1, "g")]]
    engine = SimulationEngine(
        World(network, 1),
        scripted_scheduler(network, script),
        max_turns=max_turns,
    )

    if finishes:
        assert len(engine.run()) == 2
    else:
        with pytest.raises(SimulationError, match="not finished after 1"):
            engine.run()


def test_default_turn_limit(
    write_map: WriteMap, idle_scheduler: Idle, subject_map: str
) -> None:
    """G07: the default limit is 2 * zones * nb_drones."""
    world = MapParser(write_map(subject_map)).parse()
    scheduler = idle_scheduler(world.network)

    assert default_turn_limit(world) == 70
    assert SimulationEngine(world, scheduler).max_turns == 70
    assert SimulationEngine(world, scheduler, max_turns=3).max_turns == 3


def test_illegal_order_propagates(
    make_network: MakeNetwork,
    scripted_scheduler: Scripted,
    recorder: Recorder,
) -> None:
    """G08: the engine passes on the resolver's error, state untouched."""
    network = make_network("s-a a-g", links={"s-a": 2})
    script = [[MoveOrder(1, "a")], [MoveOrder(2, "a")]]
    engine = SimulationEngine(
        World(network, 2), scripted_scheduler(network, script)
    )
    visualizer, records = recorder

    with pytest.raises(SimulationError, match="zone 'a'"):
        engine.run(visualizer)
    assert len(records) == 1
    state = engine.state
    assert state.turn_number == 1
    assert state.drones[1].current_zone == "a"
    assert state.drones[2].current_zone == "s"
    assert state.occupancy("a") == 1
    assert state.occupancy("s") == 1


def test_subject_sample_map_end_to_end(
    write_map: WriteMap,
    scripted_scheduler: Scripted,
    capsys: pytest.CaptureFixture[str],
    subject_map: str,
    subject_output: list[str],
) -> None:
    """G09: parser, engine and formatter together print the sample run."""
    world = MapParser(write_map(subject_map)).parse()
    scheduler = scripted_scheduler(
        world.network, script_from_output(subject_output)
    )

    TurnLogFormatter().emit(SimulationEngine(world, scheduler).run())

    assert capsys.readouterr().out.splitlines() == subject_output


def test_restricted_route_end_to_end(
    write_map: WriteMap,
    follower_scheduler: Follower,
    capsys: pytest.CaptureFixture[str],
    restricted_only_map: str,
) -> None:
    """G10: restricted moves print the declared connection, then the zone."""
    world = MapParser(write_map(restricted_only_map)).parse()
    engine = SimulationEngine(world, follower_scheduler(world.network))

    TurnLogFormatter().emit(engine.run())
    lines = capsys.readouterr().out.splitlines()

    # roof1 holds one drone, so each take-off waits for the previous
    # drone to leave roof1: D<n> takes off on turn 2n-1 and the last
    # drone lands in goal on turn 12.
    assert lines == [
        "D1-hub-roof1",
        "D1-roof1",
        "D1-roof2 D2-hub-roof1",
        "D1-goal D2-roof1",
        "D2-roof2 D3-hub-roof1",
        "D2-goal D3-roof1",
        "D3-roof2 D4-hub-roof1",
        "D3-goal D4-roof1",
        "D4-roof2 D5-hub-roof1",
        "D4-goal D5-roof1",
        "D5-roof2",
        "D5-goal",
    ]
    for index, line in enumerate(lines):
        for token in line.split():
            if token.endswith("-hub-roof1"):
                drone = token.split("-", 1)[0]
                assert f"{drone}-roof1" in lines[index + 1].split()


def test_engine_starts_with_every_drone_at_start(
    make_network: MakeNetwork, idle_scheduler: Idle
) -> None:
    """G11: construction places all drones and sets the default limit."""
    network = make_network("s-a a-g")
    world = World(network, 4)
    engine = SimulationEngine(world, idle_scheduler(network))

    assert engine.state.turn_number == 0
    assert engine.state.occupancy("s") == 4
    assert engine.max_turns == default_turn_limit(world)
