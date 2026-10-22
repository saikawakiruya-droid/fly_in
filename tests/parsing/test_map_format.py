"""Tests for droneflow.parsing.map_format."""

import pytest

from droneflow.models.connection import Connection
from droneflow.models.zone import Zone, ZoneRole, ZoneType
from droneflow.parsing.map_format import (
    DEFAULT_FORMAT,
    START_END_FORBIDDEN,
    DroneCount,
    Endpoints,
    FieldSpec,
    FieldValues,
    ForbiddenOption,
    LineSpec,
    ZoneBuilder,
    build_connection,
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


def _probe_spec(
    metadata: tuple[FieldSpec, ...],
    forbidden: tuple[ForbiddenOption, ...],
) -> LineSpec:
    """Build a test-only ``probe: <name>`` LineSpec with the given options."""
    return LineSpec(
        keyword="probe",
        usage="<name>",
        positional=(FieldSpec("name", to_zone_name),),
        metadata=metadata,
        builder=lambda values: DroneCount(1),
        forbidden=forbidden,
    )


def test_forbidden_defaults_to_empty() -> None:
    """F01: only start_hub/end_hub forbid options; the default is empty."""
    hub = DEFAULT_FORMAT.find("hub")
    connection = DEFAULT_FORMAT.find("connection")
    assert hub is not None
    assert connection is not None
    assert hub.forbidden == ()
    assert connection.forbidden == ()
    assert DEFAULT_FORMAT.header.forbidden == ()
    plain = LineSpec(
        keyword="probe",
        usage="<name>",
        positional=(FieldSpec("name", to_zone_name),),
        metadata=(),
        builder=lambda values: DroneCount(1),
    )
    assert plain.forbidden == ()


def test_start_end_forbidden_is_shared_by_start_and_end() -> None:
    """F02: both start_hub and end_hub carry START_END_FORBIDDEN."""
    for keyword in ("start_hub", "end_hub"):
        spec = DEFAULT_FORMAT.find(keyword)
        assert spec is not None
        assert spec.forbidden == START_END_FORBIDDEN
    assert ForbiddenOption("zone", ZoneType.BLOCKED) in START_END_FORBIDDEN
    assert all(
        option.key != "max_drones" for option in START_END_FORBIDDEN
    )


@pytest.mark.parametrize("keyword", ["start_hub", "end_hub"])
def test_start_and_end_reject_blocked_zone(keyword: str) -> None:
    """F03: building a blocked start/end raises a ValueError."""
    spec = DEFAULT_FORMAT.find(keyword)
    assert spec is not None
    with pytest.raises(
        ValueError, match=f"^{keyword} cannot have zone=blocked$"
    ):
        spec.build(["a", "0", "0"], {"zone": "blocked"})


def test_forbidden_only_matches_when_the_key_is_written() -> None:
    """F04: a default equal to the forbidden value is not rejected."""
    spec = _probe_spec(
        metadata=(FieldSpec("zone", to_zone_type, default=ZoneType.NORMAL),),
        forbidden=(ForbiddenOption("zone", ZoneType.NORMAL),),
    )
    assert spec.build(["a"], {}) == DroneCount(1)
    with pytest.raises(ValueError, match="probe cannot have zone=normal"):
        spec.build(["a"], {"zone": "normal"})


def test_forbidden_compares_converted_values_and_reports_raw() -> None:
    """F05: "05" matches a forbidden 5; the message shows "05" as written."""
    spec = _probe_spec(
        metadata=(FieldSpec("max_drones", to_positive_int, default=1),),
        forbidden=(ForbiddenOption("max_drones", 5),),
    )
    with pytest.raises(ValueError) as excinfo:
        spec.build(["a"], {"max_drones": "05"})
    assert "max_drones=05" in str(excinfo.value)
    assert spec.build(["a"], {"max_drones": "6"}) == DroneCount(1)


def test_conversion_errors_come_before_forbidden_checks() -> None:
    """F06: an unconvertible value fails before the forbidden check."""
    spec = DEFAULT_FORMAT.find("start_hub")
    assert spec is not None
    with pytest.raises(ValueError) as excinfo:
        spec.build(["s", "0", "0"], {"zone": "blocked", "max_drones": "0"})
    message = str(excinfo.value)
    assert "max_drones must be a positive integer" in message
    assert "cannot have" not in message


def test_field_values_get_returns_the_typed_value() -> None:
    """NT01: get returns the value when it has the asked type."""
    values = FieldValues({"x": 3, "zone": ZoneType.PRIORITY})
    assert values.get("x", int) == 3
    assert values.get("zone", ZoneType) is ZoneType.PRIORITY


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"x": "3"}, "field 'x' is str, not int"),
        ({}, "field 'x' is NoneType, not int"),
        ({"x": None}, "field 'x' is NoneType, not int"),
    ],
)
def test_field_values_get_rejects_wrong_or_missing(
    values: dict[str, object], message: str
) -> None:
    """NT02: another type, or no value, is a TypeError naming the field."""
    with pytest.raises(TypeError) as info:
        FieldValues(values).get("x", int)
    assert str(info.value) == message


def test_field_values_get_optional() -> None:
    """NT03: None (or absent) gives None; a value of another type does not."""
    values = FieldValues({"color": None, "name": "h", "x": 1})
    assert values.get_optional("color", str) is None
    assert values.get_optional("missing", str) is None
    assert values.get_optional("name", str) == "h"
    with pytest.raises(TypeError, match="^field 'x' is int, not str$"):
        values.get_optional("x", str)


def test_field_values_keeps_its_own_copy() -> None:
    """NT04: changing the mapping after the fact does not change the values."""
    raw: dict[str, object] = {"n": 1}
    values = FieldValues(raw)
    raw["n"] = 2
    assert values.get("n", int) == 1


def test_to_endpoints_returns_named_endpoints() -> None:
    """NT05: the two names come back as Endpoints(zone_a, zone_b)."""
    endpoints = to_endpoints("roof1-goal")
    assert endpoints == Endpoints("roof1", "goal")
    assert (endpoints.zone_a, endpoints.zone_b) == ("roof1", "goal")


def test_builders_read_through_field_values() -> None:
    """NT06: ZoneBuilder and build_connection build from FieldValues."""
    zone = ZoneBuilder(ZoneRole.HUB)(
        FieldValues(
            {
                "name": "h",
                "x": 1,
                "y": 2,
                "zone": ZoneType.NORMAL,
                "color": None,
                "max_drones": 3,
            }
        )
    )
    assert zone == Zone(
        "h", 1, 2, ZoneType.NORMAL, ZoneRole.HUB, None, max_drones=3
    )
    connection = build_connection(
        FieldValues(
            {"endpoints": Endpoints("a", "b"), "max_link_capacity": 2}
        )
    )
    assert connection == Connection("a", "b", 2)


def test_spec_and_builder_mismatch_is_a_type_error() -> None:
    """NT07: a field spec whose converter disagrees with its builder (x
    kept as text, endpoints as a tuple) is a TypeError, not a ParseError
    or a wrong model."""
    spec = LineSpec(
        keyword="probe",
        usage="probe <name> <x> <y>",
        positional=(
            FieldSpec("name", to_zone_name),
            FieldSpec("x", to_zone_name),
            FieldSpec("y", to_int),
        ),
        metadata=(
            FieldSpec("zone", to_zone_type, default=ZoneType.NORMAL),
            FieldSpec("color", to_zone_name),
        ),
        builder=ZoneBuilder(ZoneRole.START),
    )
    with pytest.raises(TypeError, match="^field 'x' is str, not int$"):
        spec.build(["h", "1", "2"], {})
    with pytest.raises(TypeError, match="^field 'endpoints' is tuple"):
        build_connection(
            FieldValues({"endpoints": ("a", "b"), "max_link_capacity": 1})
        )


def test_metadata_keys_is_a_frozenset() -> None:
    """NT08: the accepted keys are a frozenset (read-only)."""
    spec = DEFAULT_FORMAT.find("hub")
    assert spec is not None
    assert spec.metadata_keys == frozenset({"zone", "color", "max_drones"})
    assert isinstance(spec.metadata_keys, frozenset)
