"""Tests for droneflow.parsing.line_tokenizer."""

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
    assert raw.positional == ["h", "2", "3"]
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
    assert raw.positional == ["4"]
    with pytest.raises(ParseError):
        TOKENIZER.tokenize_header(line("# nb_drones: 4", number=1))
