"""Tests for droneflow.models.zone."""

import pytest

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
