"""Tests for droneflow.models.zone."""

import dataclasses

import pytest

from droneflow.models.connection import Connection
from droneflow.models.network import Network
from droneflow.models.world import World
from droneflow.models.zone import Zone, ZoneRole, ZoneType


@pytest.mark.parametrize("zone_type", [ZoneType.NORMAL, ZoneType.PRIORITY])
def test_turn_cost_is_one_for_normal_and_priority(zone_type: ZoneType) -> None:
    """normal and priority zones cost a single turn to enter."""
    assert zone_type.turn_cost == 1


def test_turn_cost_is_two_for_restricted() -> None:
    """restricted zones cost two turns to enter."""
    assert ZoneType.RESTRICTED.turn_cost == 2


def test_turn_cost_raises_for_blocked() -> None:
    """blocked zones have no turn cost; callers must not ask for one."""
    with pytest.raises(ValueError):
        ZoneType.BLOCKED.turn_cost


@pytest.mark.parametrize(
    "zone_type",
    [ZoneType.NORMAL, ZoneType.PRIORITY, ZoneType.RESTRICTED],
)
def test_is_traversable_true_for_non_blocked(zone_type: ZoneType) -> None:
    """Every zone type except blocked may be entered."""
    assert zone_type.is_traversable is True


def test_is_traversable_false_for_blocked() -> None:
    """A blocked zone may never be entered."""
    assert ZoneType.BLOCKED.is_traversable is False


@pytest.mark.parametrize("role", [ZoneRole.START, ZoneRole.END])
def test_has_unlimited_capacity_for_start_and_end(role: ZoneRole) -> None:
    """start_hub and end_hub ignore max_drones."""
    zone = Zone(name="z", x=0, y=0, zone_type=ZoneType.NORMAL, role=role)
    assert zone.has_unlimited_capacity is True


def test_has_unlimited_capacity_false_for_regular_hub() -> None:
    """A regular hub is subject to its max_drones limit."""
    zone = Zone(
        name="z", x=0, y=0, zone_type=ZoneType.NORMAL, role=ZoneRole.HUB
    )
    assert zone.has_unlimited_capacity is False


def make_zone(
    role: ZoneRole = ZoneRole.HUB,
    zone_type: ZoneType = ZoneType.NORMAL,
    max_drones: int | None = None,
) -> Zone:
    """Build a zone named z at (0, 0)."""
    return Zone(
        name="z", x=0, y=0, zone_type=zone_type, role=role,
        max_drones=max_drones,
    )


@pytest.mark.parametrize("max_drones", [3, 0, None])
def test_hub_capacity_is_max_drones(max_drones: int | None) -> None:
    """ZC01: a hub's capacity is its max_drones as it is."""
    assert make_zone(max_drones=max_drones).capacity == max_drones


@pytest.mark.parametrize("max_drones", [None, 0, 3])
@pytest.mark.parametrize("role", [ZoneRole.START, ZoneRole.END])
def test_start_and_end_capacity_is_unlimited(
    role: ZoneRole, max_drones: int | None
) -> None:
    """ZC02: start and end zones are unlimited whatever max_drones says."""
    zone = make_zone(role=role, max_drones=max_drones)

    assert zone.capacity is None
    assert zone.has_unlimited_capacity is True


@pytest.mark.parametrize(
    ("zone_type", "expected"),
    [
        (ZoneType.RESTRICTED, (1, 5)),
        (ZoneType.NORMAL, (0, 4)),
        (ZoneType.PRIORITY, (0, 4)),
        (ZoneType.BLOCKED, (0, 4)),
    ],
)
def test_arrival_turn(zone_type: ZoneType, expected: tuple[int, int]) -> None:
    """ZC03: a restricted zone is entered on the turn after the departure,
    any other on the departure turn (blocked too, without an error)."""
    zone = make_zone(zone_type=zone_type)

    assert (zone.arrival_turn(0), zone.arrival_turn(4)) == expected


def test_value_objects_are_frozen() -> None:
    """ZC04: zones, connections and worlds cannot be changed; equal zones
    are equal and hash alike."""
    zone = make_zone(max_drones=1)
    connection = Connection("a", "b")
    world = World(Network(), 1)

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(zone, "max_drones", 2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(connection, "max_link_capacity", 3)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(world, "nb_drones", 2)
    assert make_zone(max_drones=1) == zone
    assert hash(make_zone(max_drones=1)) == hash(zone)
