"""LineTokenizer: splits a map line into raw string parts (syntax only)."""

import re
from dataclasses import dataclass

from ..errors import ParseError
from .map_format import LineSpec, MapFormat
from .map_reader import SourceLine

_METADATA_BLOCK = re.compile(r"([^\[\]]*)(?:\[([^\[\]]*)\])?")


@dataclass(frozen=True)
class RawLine:
    """A syntactically valid line whose values are still plain strings.

    Attributes:
        number: 1-based line number.
        spec: The LineSpec that describes this line's kind.
        positional: The required tokens, in order.
        metadata: The ``key=value`` pairs from the bracketed block.
    """

    number: int
    spec: LineSpec
    positional: list[str]
    metadata: dict[str, str]


class LineTokenizer:
    """Checks a line's syntax against the MapFormat and splits it up."""

    def __init__(self, map_format: MapFormat) -> None:
        self._format = map_format

    def tokenize_header(self, src: SourceLine) -> RawLine:
        """Tokenize the mandatory first line (``nb_drones: <n>``)."""
        spec = self._format.header
        text = src.text.strip()
        keyword, separator, rest = text.partition(":")
        if not separator or keyword != spec.keyword:
            raise ParseError(
                src.number,
                f"the first line must be '{spec.keyword}: {spec.usage}'",
            )
        return self._split(src.number, spec, rest, text)

    def tokenize(self, src: SourceLine) -> RawLine | None:
        """Tokenize a body line; blank lines and comments return None."""
        text = src.text.strip()
        if not text or text.startswith("#"):
            return None
        keyword, separator, rest = text.partition(":")
        spec = self._format.find(keyword) if separator else None
        if spec is None:
            raise ParseError(src.number, f"unrecognized line: {text!r}")
        return self._split(src.number, spec, rest, text)

    def _split(
        self, number: int, spec: LineSpec, rest: str, text: str
    ) -> RawLine:
        main, metadata = self._split_metadata(number, rest)
        unknown = set(metadata) - spec.metadata_keys
        if unknown:
            keys = ", ".join(sorted(unknown))
            raise ParseError(number, f"unknown metadata key(s): {keys}")
        tokens = main.split()
        if len(tokens) != len(spec.positional):
            expected = f"{spec.keyword}: {spec.usage}"
            raise ParseError(number, f"expected '{expected}', got {text!r}")
        return RawLine(number, spec, tokens, metadata)

    def _split_metadata(
        self, number: int, rest: str
    ) -> tuple[str, dict[str, str]]:
        """Split ``" <main part> [key=value ...]"`` into its two halves.

        A key may appear at most once per block; a repeated key is a
        ParseError rather than "last one wins".
        """
        match = _METADATA_BLOCK.fullmatch(rest)
        if match is None:
            raise ParseError(number, "malformed metadata block")
        main, block = match.groups()
        metadata: dict[str, str] = {}
        for token in (block or "").split():
            key, _, value = token.partition("=")
            if not key or not value or "=" in value:
                raise ParseError(
                    number, f"malformed metadata entry: {token!r}"
                )
            if key in metadata:
                raise ParseError(number, f"duplicate metadata key {key!r}")
            metadata[key] = value
        return main, metadata
