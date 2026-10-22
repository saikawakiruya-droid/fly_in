"""Tests for droneflow.interchange.run_file (what a run did each turn).

Small states are built with ``place``; whole runs use the subject's
example and the real scheduler, whose turn log is ``scheduler_output``.
Decision 2026-10-22 "the parser and the simulation on their own through
JSON files" 4-6; test design ``2026-10-22_test-design-stage-files.md``
C (RR01-RR10).
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from droneflow.errors import OutputFileError, SimulationError
from droneflow.interchange.run_file import (
    RunRecorder,
    move_to_json,
    state_to_json,
)
from droneflow.models.network import Network
from droneflow.models.world import World
from droneflow.models.zone import ZoneType
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.engine import MoveDecider, SimulationEngine
from droneflow.simulation.scheduler import Scheduler
from droneflow.simulation.state import Move, SimulationState

MakeNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]
Snapshot = Callable[[SimulationState], dict[str, object]]
SchedulerMaker = Callable[[Network, Pathfinder], MoveDecider]


@pytest.fixture
def mixed_state(make_network: MakeNetwork, place: Place) -> SimulationState:
    """D1 in a, D2 delivered, D3 in flight toward r, D4 still in s."""
    network = make_network(
        "s-a a-g s-r r-g",
        types={"r": ZoneType.RESTRICTED},
        capacity={"a": 2},
    )
    return place(network, 4, at={1: "a", 2: "g"}, flying={3: ("s", "r")})


def record_run(
    world: World,
    recorder: RunRecorder,
    make_scheduler: SchedulerMaker = Scheduler,
) -> None:
    """Run the world with ``recorder`` attached.

    Raises whatever the engine raises; the recorder keeps what it saw.
    """
    pathfinder = Pathfinder(world.network)
    engine = SimulationEngine(
        world, make_scheduler(world.network, pathfinder)
    )
    engine.run(recorder)


@pytest.fixture
def example_run(
    load_world: Callable[[str], World], subject_map: str
) -> dict[str, Any]:
    """Return the JSON of the subject's example, run to the end."""
    recorder = RunRecorder()
    record_run(load_world(subject_map), recorder)
    return recorder.to_json()


def test_move_to_json() -> None:
    """RR01: a departure keeps its connection; a landing has none."""
    assert move_to_json(Move(1, "a", "s-a")) == {
        "drone_id": 1, "destination": "a", "connection": "s-a",
    }
    assert move_to_json(Move(2, "r")) == {
        "drone_id": 2, "destination": "r", "connection": None,
    }


def test_state_to_json(mixed_state: SimulationState) -> None:
    """RR02: the drones not delivered, and only them, with a count."""
    data: dict[str, Any] = state_to_json(mixed_state)

    assert data["delivered_count"] == 1
    assert data["drones"] == [
        {"drone_id": 1, "status": "at_zone", "zone": "a",
         "connection": None, "target": None},
        {"drone_id": 3, "status": "in_transit", "zone": None,
         "connection": "s-r", "target": "r"},
        {"drone_id": 4, "status": "at_zone", "zone": "s",
         "connection": None, "target": None},
    ]
    assert list(data) == ["delivered_count", "drones"]


def test_initial_state(make_network: MakeNetwork, place: Place) -> None:
    """RR03: before the first turn every drone is in the start zone."""
    state = place(make_network("s-a a-g"), 2)

    data = state_to_json(state)

    assert data["drones"] == [
        {"drone_id": n, "status": "at_zone", "zone": "s",
         "connection": None, "target": None}
        for n in (1, 2)
    ]


def test_whole_run(
    example_run: dict[str, Any], scheduler_output: list[str]
) -> None:
    """RR04: turn 0 plus every turn, ending with every drone delivered."""
    turns = example_run["turns"]

    assert example_run["format"] == "fly_in.run"
    assert example_run["version"] == 1
    assert example_run["nb_drones"] == 5
    assert example_run["complete"] is True
    assert [turn["turn"] for turn in turns] == [0, 1, 2, 3, 4, 5]
    assert turns[0]["log"] == ""
    assert turns[0]["moves"] == []
    assert [d["zone"] for d in turns[0]["drones"]] == ["hub"] * 5
    assert [turn["log"] for turn in turns[1:]] == scheduler_output
    assert turns[-1]["drones"] == []
    assert turns[-1]["delivered_count"] == 5


def test_turn_in_flight(example_run: dict[str, Any]) -> None:
    """RR05: turn 2 of the example, as shown in the README."""
    turn = example_run["turns"][2]
    d4 = next(d for d in turn["drones"] if d["drone_id"] == 4)
    m4 = next(m for m in turn["moves"] if m["drone_id"] == 4)

    assert turn["log"] == "D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1"
    assert d4 == {"drone_id": 4, "status": "in_transit", "zone": None,
                  "connection": "hub-roof1", "target": "roof1"}
    assert m4 == {"drone_id": 4, "destination": "hub-roof1",
                  "connection": "hub-roof1"}


def test_stopped_run(
    load_world: Callable[[str], World],
    subject_map: str,
    stuck_after: Callable[[int], SchedulerMaker],
) -> None:
    """RR06: a run that stops part-way is recorded as incomplete."""
    recorder = RunRecorder()

    with pytest.raises(SimulationError):
        record_run(load_world(subject_map), recorder, stuck_after(2))

    data: dict[str, Any] = recorder.to_json()

    assert data["complete"] is False
    assert [turn["turn"] for turn in data["turns"]] == [0, 1, 2]


def test_recorder_only_reads(
    mixed_state: SimulationState, snapshot: Snapshot
) -> None:
    """RR07: begin and render leave the state as it was."""
    before = snapshot(mixed_state)
    recorder = RunRecorder()

    recorder.begin(mixed_state)
    recorder.render(mixed_state, [])

    assert snapshot(mixed_state) == before


def test_to_json_is_a_copy(mixed_state: SimulationState) -> None:
    """RR08: changing the returned turns does not change the recorder."""
    recorder = RunRecorder()
    recorder.begin(mixed_state)

    first: dict[str, Any] = recorder.to_json()
    first["turns"].append({})

    again: dict[str, Any] = recorder.to_json()
    assert len(again["turns"]) == 1


def test_write(
    load_world: Callable[[str], World], subject_map: str, tmp_path: Path
) -> None:
    """RR09: the file holds to_json(); an unwritable path is an error."""
    recorder = RunRecorder()
    record_run(load_world(subject_map), recorder)
    path = tmp_path / "run.json"

    recorder.write(str(path))

    assert json.loads(path.read_text(encoding="utf-8")) == recorder.to_json()
    with pytest.raises(OutputFileError):
        recorder.write(str(tmp_path / "no_dir" / "run.json"))


def test_close_writes_nothing(
    mixed_state: SimulationState,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RR10: close does nothing; only write creates a file."""
    monkeypatch.chdir(tmp_path)
    recorder = RunRecorder()

    recorder.begin(mixed_state)
    recorder.close()

    assert list(tmp_path.iterdir()) == []
