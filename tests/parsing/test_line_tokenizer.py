"""Tests for droneflow.parsing.line_tokenizer."""

from collections.abc import Mapping

import pytest

from droneflow.errors import ParseError
from droneflow.parsing.line_tokenizer import LineTokenizer
from droneflow.parsing.map_format import DEFAULT_FORMAT
from droneflow.parsing.map_reader import SourceLine

TOKENIZER = LineTokenizer(DEFAULT_FORMAT)


def line(text: str, number: int = 2) -> SourceLine:
    """Build a SourceLine for the given text."""
    return SourceLine(number, text)


def test_splits_positional_tokens_and_metadata() -> None:
    """A hub line is cut into tokens and a key/value dictionary."""
    raw = TOKENIZER.tokenize(line("hub: h 2 3 [zone=priority color=red]"))
    assert raw is not None
    assert raw.positional == ("h", "2", "3")
    assert raw.metadata == {"zone": "priority", "color": "red"}
    assert raw.spec.keyword == "hub"


@pytest.mark.parametrize("text", ["", "   ", "# comment"])
def test_blank_lines_and_comments_return_none(text: str) -> None:
    """Lines with nothing to parse are skipped."""
    assert TOKENIZER.tokenize(line(text)) is None


@pytest.mark.parametrize(
    "text",
    [
        "portal: p 2 2",
        "hub",
        "nb_drones: 3",
        "hub: h 2",
        "hub: h 2 2 3",
        "connection: a b",
        "hub: h 1 1 [color=red",
        "hub: h 1 1 [zone]",
        "hub: h 1 1 [zone=]",
        "hub: h 1 1 [a=b=c]",
        "hub: h 1 1 [colr=red]",
        "connection: a-b [color=red]",
    ],
)
def test_syntax_errors_carry_the_line_number(text: str) -> None:
    """Every syntax problem is reported with the offending line number."""
    with pytest.raises(ParseError) as excinfo:
        TOKENIZER.tokenize(line(text, number=7))
    assert excinfo.value.line_number == 7


def test_header_is_tokenized_separately() -> None:
    """The first line must be nb_drones, even if it is a comment."""
    raw = TOKENIZER.tokenize_header(line("nb_drones: 4", number=1))
    assert raw.positional == ("4",)
    with pytest.raises(ParseError):
        TOKENIZER.tokenize_header(line("# nb_drones: 4", number=1))


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("hub: h 1 1 [zone=normal zone=priority]", "zone"),
        ("start_hub: s 0 0 [color=red color=blue]", "color"),
        ("end_hub: e 1 1 [max_drones=2 max_drones=3]", "max_drones"),
        (
            "connection: a-b [max_link_capacity=1 max_link_capacity=2]",
            "max_link_capacity",
        ),
    ],
)
def test_duplicate_metadata_key_is_rejected_on_every_line_kind(
    text: str, key: str
) -> None:
    """T01: a key repeated in one block is a syntax error for every line."""
    with pytest.raises(ParseError) as excinfo:
        TOKENIZER.tokenize(line(text, number=7))
    assert excinfo.value.line_number == 7
    assert str(excinfo.value) == f"line 7: duplicate metadata key '{key}'"


@pytest.mark.parametrize(
    "text",
    [
        "hub: h 1 1 [zone=normal zone=normal]",
        "hub: h 1 1 [zone=normal color=red zone=normal]",
    ],
)
def test_duplicate_metadata_key_is_rejected_even_with_the_same_value(
    text: str,
) -> None:
    """T02: repeating a key is rejected even if the value is identical."""
    with pytest.raises(ParseError) as excinfo:
        TOKENIZER.tokenize(line(text, number=7))
    assert str(excinfo.value) == "line 7: duplicate metadata key 'zone'"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hub: h 1 1 [zone=a zone=]", "malformed metadata entry: 'zone='"),
        (
            "hub: h 1 1 [color= zone=a zone=b]",
            "malformed metadata entry: 'color='",
        ),
        (
            "hub: h 1 1 [zone=a zone=b color=]",
            "duplicate metadata key 'zone'",
        ),
    ],
)
def test_duplicate_and_malformed_entries_report_the_first_problem(
    text: str, expected: str
) -> None:
    """T03: entries are checked left to right, malformed before duplicate."""
    with pytest.raises(ParseError) as excinfo:
        TOKENIZER.tokenize(line(text, number=7))
    assert str(excinfo.value) == f"line 7: {expected}"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hub: h 1 1 [colr=x colr=y]", "duplicate metadata key 'colr'"),
        ("hub: h 1 1 [colr=x zone=a zone=b]", "duplicate metadata key 'zone'"),
        ("hub: h 1 1 [zone=a Zone=b]", "unknown metadata key(s): Zone"),
    ],
)
def test_duplicate_key_is_reported_before_unknown_key(
    text: str, expected: str
) -> None:
    """T04: duplicates are found while reading, unknown keys afterwards.

    Keys are case-sensitive, so ``zone`` and ``Zone`` are not duplicates.
    """
    with pytest.raises(ParseError) as excinfo:
        TOKENIZER.tokenize(line(text, number=7))
    assert str(excinfo.value) == f"line 7: {expected}"


def test_raw_line_holds_a_tuple_and_a_mapping() -> None:
    """NT09: positional is a tuple, metadata a Mapping (read-only types)."""
    raw = TOKENIZER.tokenize(line("connection: a-b [max_link_capacity=2]"))
    assert raw is not None
    assert isinstance(raw.positional, tuple)
    assert raw.positional == ("a-b",)
    assert isinstance(raw.metadata, Mapping)
    assert dict(raw.metadata) == {"max_link_capacity": "2"}
