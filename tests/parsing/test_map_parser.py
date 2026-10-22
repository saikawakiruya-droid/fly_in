"""Tests for droneflow.parsing.map_parser."""

from pathlib import Path

import pytest

from droneflow.errors import ParseError, UnreachableGoalError
from droneflow.models.zone import ZoneRole, ZoneType
from droneflow.parsing.map_parser import MapParser

MINIMAL_MAP = "nb_drones: 1\nstart_hub: s 0 0\nend_hub: e 1 1\n"

SUBJECT_SAMPLE_MAP = """\
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
hub: tunnelB 7 4 [zone=normal color=red]
hub: obstacleX 5 5 [zone=blocked color=gray]
connection: hub-roof1
connection: hub-corridorA
connection: roof1-roof2
connection: roof2-goal
connection: corridorA-tunnelB [max_link_capacity=2]
connection: tunnelB-goal
"""


def write_map(tmp_path: Path, text: str) -> Path:
    """Write ``text`` to a map file under tmp_path and return its path."""
    path = tmp_path / "map.txt"
    path.write_text(text)
    return path


def test_parses_the_subject_sample_map(tmp_path: Path) -> None:
    """The exact example map from the subject parses without error."""
    world = MapParser(write_map(tmp_path, SUBJECT_SAMPLE_MAP)).parse()

    assert world.nb_drones == 5
    assert set(world.network.zones) == {
        "hub",
        "goal",
        "roof1",
        "roof2",
        "corridorA",
        "tunnelB",
        "obstacleX",
    }
    assert world.network.start_zone.name == "hub"
    assert world.network.end_zone.name == "goal"

    roof1 = world.network.get_zone("roof1")
    assert roof1.zone_type is ZoneType.RESTRICTED
    assert roof1.color == "red"

    obstacle = world.network.get_zone("obstacleX")
    assert obstacle.zone_type is ZoneType.BLOCKED

    corridor = world.network.get_zone("corridorA")
    assert corridor.max_drones == 2

    connections = {
        frozenset({c.zone_a, c.zone_b}): c.max_link_capacity
        for c in world.network.connections
    }
    assert connections[frozenset({"corridorA", "tunnelB"})] == 2
    assert connections[frozenset({"hub", "roof1"})] == 1


def test_comments_and_blank_lines_are_ignored(tmp_path: Path) -> None:
    """Comment lines and blank lines between entries are skipped."""
    text = (
        "nb_drones: 1\n"
        "# a comment\n"
        "\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 1\n"
    )
    world = MapParser(write_map(tmp_path, text)).parse()
    assert set(world.network.zones) == {"s", "e"}


def test_zone_type_defaults_to_normal_when_omitted(tmp_path: Path) -> None:
    """A hub line with no zone= metadata is a normal zone."""
    text = MINIMAL_MAP + "hub: h 2 2\n"
    world = MapParser(write_map(tmp_path, text)).parse()
    assert world.network.get_zone("h").zone_type is ZoneType.NORMAL


def test_color_defaults_to_none_when_omitted(tmp_path: Path) -> None:
    """A hub line with no color= metadata has no color set."""
    text = MINIMAL_MAP + "hub: h 2 2\n"
    world = MapParser(write_map(tmp_path, text)).parse()
    assert world.network.get_zone("h").color is None


def test_max_drones_defaults_to_one_for_a_regular_hub(tmp_path: Path) -> None:
    """A hub line with no max_drones= metadata caps occupancy at 1."""
    text = MINIMAL_MAP + "hub: h 2 2\n"
    world = MapParser(write_map(tmp_path, text)).parse()
    assert world.network.get_zone("h").max_drones == 1


@pytest.mark.parametrize("keyword", ["start_hub", "end_hub"])
def test_max_drones_is_normalized_to_none_for_start_and_end(
    tmp_path: Path, keyword: str
) -> None:
    """An explicit max_drones= on start_hub/end_hub is discarded."""
    other_keyword = "end_hub" if keyword == "start_hub" else "start_hub"
    text = (
        "nb_drones: 1\n"
        f"{keyword}: a 0 0 [max_drones=5]\n"
        f"{other_keyword}: b 1 1\n"
    )
    world = MapParser(write_map(tmp_path, text)).parse()
    assert world.network.get_zone("a").max_drones is None


def test_max_link_capacity_defaults_to_one_when_omitted(
    tmp_path: Path,
) -> None:
    """A connection line with no max_link_capacity= metadata defaults to 1."""
    text = MINIMAL_MAP + "connection: s-e\n"
    world = MapParser(write_map(tmp_path, text)).parse()
    assert world.network.connections[0].max_link_capacity == 1


def test_duplicate_zone_name_raises_parse_error(tmp_path: Path) -> None:
    """Two zones sharing a name is a parser constraint violation."""
    text = MINIMAL_MAP + "hub: s 2 2\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 4


def test_duplicate_connection_raises_parse_error(tmp_path: Path) -> None:
    """a-b and b-a are the same connection and cannot both be declared."""
    text = MINIMAL_MAP + "connection: s-e\nconnection: e-s\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 5


def test_self_loop_connection_is_allowed(tmp_path: Path) -> None:
    """A connection from a zone to itself is not rejected by the parser."""
    text = MINIMAL_MAP + "connection: s-s\n"
    world = MapParser(write_map(tmp_path, text)).parse()
    assert len(world.network.connections) == 1


def test_duplicate_coordinates_are_allowed(tmp_path: Path) -> None:
    """Two distinct zones may share the same (x, y) coordinates."""
    text = MINIMAL_MAP + "hub: h 0 0\n"
    world = MapParser(write_map(tmp_path, text)).parse()
    assert world.network.get_zone("h").x == 0
    assert world.network.get_zone("h").y == 0


def test_missing_start_hub_raises_parse_error(tmp_path: Path) -> None:
    """A map without a start_hub cannot be parsed."""
    text = "nb_drones: 1\nend_hub: e 1 1\n"
    with pytest.raises(ParseError):
        MapParser(write_map(tmp_path, text)).parse()


def test_missing_end_hub_raises_parse_error(tmp_path: Path) -> None:
    """A map without an end_hub cannot be parsed."""
    text = "nb_drones: 1\nstart_hub: s 0 0\n"
    with pytest.raises(ParseError):
        MapParser(write_map(tmp_path, text)).parse()


@pytest.mark.parametrize("keyword", ["start_hub", "end_hub"])
def test_duplicate_start_or_end_hub_raises_parse_error(
    tmp_path: Path, keyword: str
) -> None:
    """A second start_hub or end_hub line is rejected immediately."""
    text = MINIMAL_MAP + f"{keyword}: extra 2 2\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 4


def test_unknown_zone_type_raises_parse_error(tmp_path: Path) -> None:
    """A zone= value outside the four known types is a parse error."""
    text = MINIMAL_MAP + "hub: h 2 2 [zone=weird]\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 4


def test_unknown_metadata_key_on_zone_line_raises_parse_error(
    tmp_path: Path,
) -> None:
    """A metadata key that isn't zone/color/max_drones is rejected."""
    text = MINIMAL_MAP + "hub: h 2 2 [colr=red]\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 4


def test_unknown_metadata_key_on_connection_line_raises_parse_error(
    tmp_path: Path,
) -> None:
    """A metadata key other than max_link_capacity is rejected."""
    text = MINIMAL_MAP + "connection: s-e [color=red]\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 4


def test_connection_to_unknown_zone_raises_parse_error(
    tmp_path: Path,
) -> None:
    """A connection cannot reference a zone that was never declared."""
    text = MINIMAL_MAP + "connection: s-ghost\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 4


def test_first_line_must_be_nb_drones(tmp_path: Path) -> None:
    """A map that doesn't start with nb_drones: is rejected."""
    text = "start_hub: s 0 0\nend_hub: e 1 1\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 1


def test_nb_drones_must_be_a_positive_integer(tmp_path: Path) -> None:
    """nb_drones: 0 is not a valid drone count."""
    text = "nb_drones: 0\nstart_hub: s 0 0\nend_hub: e 1 1\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 1


def test_zone_name_with_dash_raises_parse_error(tmp_path: Path) -> None:
    """Dashes are reserved for the connection syntax and forbidden in names."""
    text = "nb_drones: 1\nstart_hub: a-b 0 0\nend_hub: e 1 1\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 2


def test_non_integer_coordinate_raises_parse_error(tmp_path: Path) -> None:
    """A non-integer x or y coordinate is a parse error."""
    text = "nb_drones: 1\nstart_hub: s zero 0\nend_hub: e 1 1\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 2


def test_malformed_metadata_block_raises_parse_error(
    tmp_path: Path,
) -> None:
    """An unterminated metadata bracket is a parse error."""
    text = "nb_drones: 1\nstart_hub: s 0 0 [color=green\nend_hub: e 1 1\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 2


def test_malformed_metadata_entry_raises_parse_error(
    tmp_path: Path,
) -> None:
    """A metadata token without a single '=' is a parse error."""
    text = MINIMAL_MAP + "hub: h 2 2 [zone]\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 4


def test_unrecognized_keyword_raises_parse_error(tmp_path: Path) -> None:
    """A line that matches none of the known keywords is a parse error."""
    text = MINIMAL_MAP + "portal: p 2 2\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 4


def test_empty_file_raises_parse_error(tmp_path: Path) -> None:
    """An empty map file is rejected rather than crashing."""
    with pytest.raises(ParseError):
        MapParser(write_map(tmp_path, "")).parse()


def test_hub_role_is_used_for_plain_hub_lines(tmp_path: Path) -> None:
    """A hub: line produces a zone with the HUB role."""
    text = MINIMAL_MAP + "hub: h 2 2\n"
    world = MapParser(write_map(tmp_path, text)).parse()
    assert world.network.get_zone("h").role is ZoneRole.HUB


def test_keyword_without_colon_raises_parse_error(tmp_path: Path) -> None:
    """A bare keyword with no colon is a parse error, not a crash."""
    text = MINIMAL_MAP + "hub\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 4


def test_blocked_start_hub_raises_parse_error(tmp_path: Path) -> None:
    """M01: start_hub with zone=blocked is rejected on its own line."""
    text = "nb_drones: 1\nstart_hub: s 0 0 [zone=blocked]\nend_hub: e 1 1\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 2
    assert str(excinfo.value) == "line 2: start_hub cannot have zone=blocked"


def test_blocked_end_hub_reports_the_physical_line(tmp_path: Path) -> None:
    """M02: end_hub is rejected too; comments and blanks count as lines."""
    text = (
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "# comment\n"
        "\n"
        "end_hub: e 1 1 [zone=blocked]\n"
    )
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 5
    assert "end_hub cannot have zone=blocked" in str(excinfo.value)


@pytest.mark.parametrize(
    "metadata",
    [
        "[zone=blocked color=red]",
        "[color=red zone=blocked]",
        "[max_drones=3 color=gray zone=blocked]",
    ],
)
def test_blocked_start_hub_is_rejected_regardless_of_other_options(
    tmp_path: Path, metadata: str
) -> None:
    """M03: other keys and their order do not hide zone=blocked."""
    text = f"nb_drones: 1\nstart_hub: s 0 0 {metadata}\nend_hub: e 1 1\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 2
    assert "start_hub cannot have zone=blocked" in str(excinfo.value)


def test_blocked_regular_hub_is_still_allowed(tmp_path: Path) -> None:
    """M04: the ban applies to start/end only; a blocked hub is valid."""
    text = MINIMAL_MAP + "hub: h 2 2 [zone=blocked]\n"
    world = MapParser(write_map(tmp_path, text)).parse()
    assert world.network.get_zone("h").zone_type is ZoneType.BLOCKED


@pytest.mark.parametrize("keyword", ["start_hub", "end_hub"])
@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (" [zone=normal]", ZoneType.NORMAL),
        (" [zone=restricted]", ZoneType.RESTRICTED),
        (" [zone=priority]", ZoneType.PRIORITY),
        ("", ZoneType.NORMAL),
    ],
)
def test_start_and_end_accept_non_blocked_zone_types(
    tmp_path: Path, keyword: str, metadata: str, expected: ZoneType
) -> None:
    """M05: every zone type other than blocked (or none) is accepted."""
    other_keyword = "end_hub" if keyword == "start_hub" else "start_hub"
    text = (
        "nb_drones: 1\n"
        f"{keyword}: a 0 0{metadata}\n"
        f"{other_keyword}: b 1 1\n"
    )
    world = MapParser(write_map(tmp_path, text)).parse()
    assert world.network.get_zone("a").zone_type is expected


@pytest.mark.parametrize("keyword", ["start_hub", "end_hub"])
def test_start_and_end_ignore_max_drones_alongside_other_options(
    tmp_path: Path, keyword: str
) -> None:
    """M06: max_drones is still discarded next to an allowed zone type."""
    other_keyword = "end_hub" if keyword == "start_hub" else "start_hub"
    text = (
        "nb_drones: 1\n"
        f"{keyword}: a 0 0 [zone=priority max_drones=5]\n"
        f"{other_keyword}: b 1 1\n"
    )
    world = MapParser(write_map(tmp_path, text)).parse()
    zone = world.network.get_zone("a")
    assert zone.max_drones is None
    assert zone.zone_type is ZoneType.PRIORITY


def test_blocked_goal_fails_at_parse_time_not_pathfinding(
    tmp_path: Path,
) -> None:
    """M07: a blocked end_hub is a ParseError, before any Pathfinder runs."""
    text = (
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: g 1 1 [zone=blocked]\n"
        "connection: s-g\n"
    )
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 3
    assert not isinstance(excinfo.value, UnreachableGoalError)


@pytest.mark.parametrize("keyword", ["start_hub", "end_hub"])
@pytest.mark.parametrize("raw", ["0", "-1", "two"])
def test_start_and_end_still_validate_ignored_max_drones(
    tmp_path: Path, keyword: str, raw: str
) -> None:
    """M08: max_drones is ignored on start/end but must still be valid.

    VII.4 requires capacity values to be positive integers, so a bad value
    is a ParseError even though the value itself is discarded.
    """
    other_keyword = "end_hub" if keyword == "start_hub" else "start_hub"
    text = (
        "nb_drones: 1\n"
        f"{keyword}: a 0 0 [max_drones={raw}]\n"
        f"{other_keyword}: b 1 1\n"
    )
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 2
    assert "max_drones must be" in str(excinfo.value)


@pytest.mark.parametrize(
    "metadata", ["[zone=blocked zone=normal]", "[zone=normal zone=blocked]"]
)
def test_blocked_cannot_be_hidden_by_a_repeated_zone_key(
    tmp_path: Path, metadata: str
) -> None:
    """Duplicate key M01: a later zone= no longer overrides zone=blocked.

    Both orders fail with the same duplicate-key message, not the
    start_hub blocked message.
    """
    text = f"nb_drones: 1\nstart_hub: s 0 0 {metadata}\nend_hub: e 1 1\n"
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 2
    assert str(excinfo.value) == "line 2: duplicate metadata key 'zone'"


def test_duplicate_zone_key_on_end_hub_reports_the_physical_line(
    tmp_path: Path,
) -> None:
    """Duplicate key M02: end_hub is checked too, on its physical line."""
    text = (
        "nb_drones: 1\n"
        "# comment\n"
        "start_hub: s 0 0\n"
        "\n"
        "end_hub: e 1 1 [zone=blocked zone=normal]\n"
    )
    with pytest.raises(ParseError) as excinfo:
        MapParser(write_map(tmp_path, text)).parse()
    assert excinfo.value.line_number == 5
    assert str(excinfo.value) == "line 5: duplicate metadata key 'zone'"


def test_metadata_blocks_without_duplicates_still_parse(
    tmp_path: Path,
) -> None:
    """Duplicate key M03: distinct keys in one block are unaffected."""
    text = (
        MINIMAL_MAP
        + "hub: h 2 2 [zone=priority color=red max_drones=2]\n"
        + "connection: s-h [max_link_capacity=3]\n"
    )
    world = MapParser(write_map(tmp_path, text)).parse()
    hub = world.network.get_zone("h")
    assert hub.zone_type is ZoneType.PRIORITY
    assert hub.color == "red"
    assert hub.max_drones == 2
    (connection,) = world.network.connections
    assert connection.max_link_capacity == 3


# --- byte order mark (utf-8-sig) --------------------------------------


BOM = b"\xef\xbb\xbf"


def write_bytes(tmp_path: Path, data: bytes) -> Path:
    """Write raw bytes to a map file under tmp_path and return its path."""
    path = tmp_path / "map.txt"
    path.write_bytes(data)
    return path


def test_leading_bom_is_skipped(tmp_path: Path) -> None:
    """BM01: a map saved with a byte order mark parses as without one."""
    path = write_bytes(tmp_path, BOM + SUBJECT_SAMPLE_MAP.encode())

    world = MapParser(path).parse()

    assert world.nb_drones == 5
    assert next(iter(world.network.zones)) == "hub"


def test_bom_with_crlf_line_ends(tmp_path: Path) -> None:
    """BM02: a byte order mark and CRLF line ends together still parse."""
    text = SUBJECT_SAMPLE_MAP.replace("\n", "\r\n")
    path = write_bytes(tmp_path, BOM + text.encode())

    assert MapParser(path).parse().nb_drones == 5


def test_only_one_leading_bom_is_skipped(tmp_path: Path) -> None:
    """BM03: a second byte order mark, or one at the start of another line,
    is an error as before."""
    twice = write_bytes(tmp_path, BOM + BOM + SUBJECT_SAMPLE_MAP.encode())
    with pytest.raises(ParseError) as first:
        MapParser(twice).parse()
    assert str(first.value) == (
        "line 1: the first line must be 'nb_drones: <n>'"
    )

    lines = SUBJECT_SAMPLE_MAP.splitlines(keepends=True)
    lines[5] = "\ufeff" + lines[5]
    inside = write_bytes(tmp_path, "".join(lines).encode())
    with pytest.raises(ParseError) as sixth:
        MapParser(inside).parse()
    assert str(sixth.value) == (
        "line 6: unrecognized line: "
        "'\\ufeffhub: roof2 6 2 [zone=normal color=blue]'"
    )
