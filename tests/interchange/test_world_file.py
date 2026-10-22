"""Tests for droneflow.interchange.world_file (World <-> JSON).

Invalid worlds are made from the subject's example by changing exactly
one thing, so each case shows which check rejects it. Zones of the
example in declaration order: 0 hub, 1 goal, 2 roof1, 3 roof2,
4 corridorA, 5 tunnelB, 6 obstacleX; connections: 0 hub-roof1,
1 hub-corridorA, 2 roof1-roof2, 3 roof2-goal, 4 corridorA-tunnelB,
5 tunnelB-goal. Decision 2026-10-22 "the parser and the simulation on
their own through JSON files" 2 and 3; test design
``2026-10-22_test-design-stage-files.md`` B (WF01-WF09).
"""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from droneflow.errors import WorldFileError
from droneflow.interchange.world_file import (
    WorldFile,
    world_from_json,
    world_to_json,
)
from droneflow.models.world import World

LoadWorld = Callable[[str], World]
Mutation = Callable[[Any], Any]


@pytest.fixture
def world(load_world: LoadWorld, subject_map: str) -> World:
    """Return the subject's example, parsed."""
    return load_world(subject_map)


def assert_same_world(actual: World, expected: World) -> None:
    """Compare zones (in order), connections and the drone count."""
    assert list(actual.network.zones.values()) == list(
        expected.network.zones.values()
    )
    assert list(actual.network.zones) == list(expected.network.zones)
    assert list(actual.network.connections) == list(
        expected.network.connections
    )
    assert actual.nb_drones == expected.nb_drones


def test_round_trip(world: World) -> None:
    """WF01: the World read back equals the one written."""
    assert_same_world(world_from_json(world_to_json(world)), world)


def test_json_shape(world: World) -> None:
    """WF02: every field, in declaration order, as plain values."""
    data = world_to_json(world)

    assert list(data) == [
        "format", "version", "nb_drones", "zones", "connections",
    ]
    assert data["format"] == "fly_in.world"
    assert data["version"] == 1
    assert data["nb_drones"] == 5
    zones = data["zones"]
    connections = data["connections"]
    assert isinstance(zones, list) and isinstance(connections, list)
    assert zones[0] == {
        "name": "hub", "x": 0, "y": 0, "zone_type": "normal",
        "role": "start_hub", "color": "green", "max_drones": None,
    }
    assert zones[4] == {
        "name": "corridorA", "x": 4, "y": 3, "zone_type": "priority",
        "role": "hub", "color": "green", "max_drones": 2,
    }
    assert connections[4] == {
        "zone_a": "corridorA", "zone_b": "tunnelB", "max_link_capacity": 2,
    }


def test_round_trip_through_text(world: World) -> None:
    """WF03: the same after going through a JSON string."""
    text = json.dumps(world_to_json(world))
    assert_same_world(world_from_json(json.loads(text)), world)


def _set(path: str, value: object) -> Mutation:
    """Return a mutation setting ``data[a][i][b] = value`` for "a.i.b"."""
    *parents, last = path.split(".")

    def mutate(data: Any) -> Any:
        target = data
        for key in parents:
            target = target[int(key) if key.isdigit() else key]
        target[int(last) if last.isdigit() else last] = value
        return data

    return mutate


def _delete_key(key: str) -> Mutation:
    def mutate(data: Any) -> Any:
        del data[key]
        return data

    return mutate


def _add_connection(data: Any) -> Any:
    data["connections"].append(
        {"zone_a": "roof1", "zone_b": "hub", "max_link_capacity": 1}
    )
    return data


def _remove_goal(data: Any) -> Any:
    del data["zones"][1]
    del data["connections"][5]
    del data["connections"][3]
    return data


INVALID = [
    ("a", lambda data: [], "top level: must be an object"),
    ("b", _set("format", "fly_in.run"), "format: must be 'fly_in.world'"),
    ("c", _set("version", 2), "version: must be 1"),
    ("d", _set("nb_drones", 0), "nb_drones: must be a positive integer"),
    ("e", _delete_key("zones"), "zones: missing"),
    ("f", _set("zones.2.x", "3"), "zones[2].x: must be an integer"),
    (
        "g",
        _set("zones.2.name", "roof-1"),
        "zones[2].name: must not contain '-', got 'roof-1'",
    ),
    (
        "h",
        _set("zones.3.name", "roof1"),
        "zones[3].name: duplicate zone name: roof1",
    ),
    (
        "i",
        _set("zones.2.role", "start_hub"),
        "zones[2].name: duplicate start_hub",
    ),
    (
        "j",
        _set("zones.2.zone_type", "lava"),
        "zones[2].zone_type: must be one of normal, blocked, restricted, "
        "priority, got 'lava'",
    ),
    (
        "k",
        _set("zones.2.max_drones", 0),
        "zones[2].max_drones: must be a positive integer",
    ),
    (
        "l",
        _set("zones.2.max_drones", None),
        "zones[2].max_drones: must be an integer",
    ),
    (
        "m",
        _set("zones.0.zone_type", "blocked"),
        "zones[0].zone_type: start_hub cannot be blocked",
    ),
    (
        "n",
        _set("zones.1.zone_type", "blocked"),
        "zones[1].zone_type: end_hub cannot be blocked",
    ),
    ("o", _set("zones.2.color", 1), "zones[2].color: must be a string"),
    (
        "p",
        _set("connections.0.zone_b", "nowhere"),
        "connections[0].zone_a: unknown zone: nowhere",
    ),
    (
        "q",
        _add_connection,
        "connections[6].zone_a: duplicate connection: roof1-hub",
    ),
    (
        "r",
        _set("connections.4.max_link_capacity", 0),
        "connections[4].max_link_capacity: must be a positive integer",
    ),
    ("s", _remove_goal, "zones: missing end_hub"),
]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [(mutate, message) for _, mutate, message in INVALID],
    ids=[case for case, _, _ in INVALID],
)
def test_invalid_world(
    world: World, mutate: Mutation, message: str
) -> None:
    """WF04: one changed field is rejected with where and why."""
    data = mutate(copy.deepcopy(world_to_json(world)))

    with pytest.raises(ValueError) as info:
        world_from_json(data)

    assert str(info.value) == message


def test_start_capacity_is_ignored(world: World) -> None:
    """WF05: max_drones on start/end is ignored, as on a map line."""
    data = _set("zones.0.max_drones", 3)(world_to_json(world))

    loaded = world_from_json(data)

    assert loaded.network.get_zone("hub").max_drones is None


def test_world_file_round_trip(world: World, tmp_path: Path) -> None:
    """WF06: write then read through a file gives the same World."""
    path = str(tmp_path / "w.json")

    WorldFile(path).write(world)

    assert_same_world(WorldFile(path).read(), world)
    text = (tmp_path / "w.json").read_text(encoding="utf-8")
    assert text.startswith('{\n  "format": "fly_in.world",')


def test_not_json(tmp_path: Path) -> None:
    """WF07: a file that is not JSON is a WorldFileError."""
    file = tmp_path / "map.txt"
    file.write_text("nb_drones: 5\n", encoding="utf-8")
    path = str(file)

    with pytest.raises(WorldFileError) as info:
        WorldFile(path).read()

    assert info.value.path == path
    assert str(info.value) == (
        f"invalid world file '{path}': not JSON: Expecting value (line 1)"
    )


def test_invalid_world_file(world: World, tmp_path: Path) -> None:
    """WF08: an invalid world in a file gives the reason as it is."""
    file = tmp_path / "w.json"
    data = _set("nb_drones", 0)(world_to_json(world))
    file.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(WorldFileError) as info:
        WorldFile(str(file)).read()

    assert info.value.reason == "nb_drones: must be a positive integer"


def test_unreadable_file(tmp_path: Path) -> None:
    """WF09: opening and decoding errors are left to the caller."""
    with pytest.raises(FileNotFoundError):
        WorldFile(str(tmp_path / "none.json")).read()
    binary = tmp_path / "bin.json"
    binary.write_bytes(b"\xff")
    with pytest.raises(UnicodeDecodeError):
        WorldFile(str(binary)).read()
