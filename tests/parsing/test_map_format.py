"""Tests for droneflow.parsing.map_format."""

import pytest

from droneflow.models.connection import Connection
from droneflow.models.zone import Zone, ZoneRole, ZoneType
from droneflow.parsing.map_format import (
    DEFAULT_FORMAT,
    DroneCount,
    FieldSpec,
    to_endpoints,
    to_int,
    to_positive_int,
    to_zone_name,
    to_zone_type,
)


def test_to_int_rejects_non_integers() -> None:
    """A non-numeric string is a ValueError, not a crash."""
    with pytest.raises(ValueError):
        to_int("zero")


@pytest.mark.parametrize("raw", ["0", "-3"])
def test_to_positive_int_rejects_zero_and_negatives(raw: str) -> None:
    """Zero and negative numbers are not positive integers."""
    with pytest.raises(ValueError):
        to_positive_int(raw)


def test_to_zone_name_rejects_dashes() -> None:
    """Dashes are reserved for the connection syntax."""
    with pytest.raises(ValueError):
        to_zone_name("a-b")


def test_to_zone_type_rejects_unknown_values() -> None:
    """Only the four known zone types are accepted."""
    assert to_zone_type("priority") is ZoneType.PRIORITY
    with pytest.raises(ValueError):
        to_zone_type("weird")


@pytest.mark.parametrize("raw", ["a", "a-", "-b", "a-b-c"])
def test_to_endpoints_rejects_malformed_pairs(raw: str) -> None:
    """Exactly one dash with a non-empty name on each side is required."""
    with pytest.raises(ValueError):
        to_endpoints(raw)


def test_field_spec_returns_default_when_raw_is_absent() -> None:
    """An absent optional field falls back to its default."""
    assert FieldSpec("n", to_int, default=7).read(None) == 7


def test_field_spec_error_names_the_field() -> None:
    """A conversion failure mentions which field was wrong."""
    with pytest.raises(ValueError, match="x must be an integer"):
        FieldSpec("x", to_int).read("zero")


def test_hub_defaults_max_drones_to_one() -> None:
    """A regular hub with no metadata gets capacity 1."""
    spec = DEFAULT_FORMAT.find("hub")
    assert spec is not None
    entry = spec.build(["h", "1", "2"], {})
    assert isinstance(entry, Zone)
    assert entry.role is ZoneRole.HUB
    assert entry.max_drones == 1


def test_start_hub_discards_max_drones() -> None:
    """start_hub always ends up with unlimited capacity (None)."""
    spec = DEFAULT_FORMAT.find("start_hub")
    assert spec is not None
    entry = spec.build(["s", "0", "0"], {"max_drones": "5"})
    assert isinstance(entry, Zone)
    assert entry.max_drones is None


def test_connection_builds_with_default_capacity() -> None:
    """A connection with no metadata gets max_link_capacity 1."""
    spec = DEFAULT_FORMAT.find("connection")
    assert spec is not None
    entry = spec.build(["a-b"], {})
    assert entry == Connection("a", "b", 1)


def test_header_builds_a_drone_count() -> None:
    """The header spec yields a DroneCount, and nb_drones is not a body key."""
    entry = DEFAULT_FORMAT.header.build(["3"], {})
    assert entry == DroneCount(3)
    assert DEFAULT_FORMAT.find("nb_drones") is None
