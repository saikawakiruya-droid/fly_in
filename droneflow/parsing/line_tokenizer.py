"""LineTokenizer: splits a map line into raw string parts (syntax only)."""

import re
from collections.abc import Mapping
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
    positional: tuple[str, ...]
    metadata: Mapping[str, str]


class LineTokenizer:
    """Splits map lines into parts, rejecting any that break the MapFormat."""

    def __init__(self, map_format: MapFormat) -> None:
        """Check lines against ``map_format``.

        Args:
            map_format: The line kinds the map may contain.
        """
        self._format = map_format

    def tokenize_header(self, line: SourceLine) -> RawLine:
        """Tokenize the mandatory first line (``nb_drones: <n>``).

        Args:
            line: The first line of the file.

        Returns:
            The header split into its parts.

        Raises:
            droneflow.errors.ParseError: If the line is not the header, or
                its parts do not match the header's usage.
        """
        spec = self._format.header
        text = line.text.strip()
        keyword, separator, rest = text.partition(":")
        if not separator or keyword != spec.keyword:
            raise ParseError(
                line.number,
                f"the first line must be '{spec.keyword}: {spec.usage}'",
            )
        return self._split(line.number, spec, rest, text)

    def tokenize(self, line: SourceLine) -> RawLine | None:
        """Tokenize a body line; blank lines and comments return None.

        Args:
            line: A line after the header.

        Returns:
            The line split into its parts, or None for a blank line or a
            comment.

        Raises:
            droneflow.errors.ParseError: If the keyword is unknown or the
                parts do not match its usage.
        """
        text = line.text.strip()
        if not text or text.startswith("#"):
            return None
        keyword, separator, rest = text.partition(":")
        spec = self._format.find(keyword) if separator else None
        if spec is None:
            raise ParseError(line.number, f"unrecognized line: {text!r}")
        return self._split(line.number, spec, rest, text)

    def _split(
        self, number: int, spec: LineSpec, rest: str, text: str
    ) -> RawLine:
        """Split the text after the keyword into tokens and metadata.

        Args:
            number: The line number, for errors.
            spec: The kind of line the keyword named.
            rest: The text after ``keyword:``.
            text: The whole stripped line, quoted in errors.

        Returns:
            The checked line with its tokens and metadata.

        Raises:
            droneflow.errors.ParseError: If a metadata key is not allowed
                for this kind of line, or the token count is wrong.
        """
        main, metadata = self._split_metadata(number, rest)
        unknown = set(metadata) - spec.metadata_keys
        if unknown:
            keys = ", ".join(sorted(unknown))
            raise ParseError(number, f"unknown metadata key(s): {keys}")
        tokens = main.split()
        if len(tokens) != len(spec.positional):
            expected = f"{spec.keyword}: {spec.usage}"
            raise ParseError(number, f"expected '{expected}', got {text!r}")
        return RawLine(number, spec, tuple(tokens), metadata)

    def _split_metadata(
        self, number: int, rest: str
    ) -> tuple[str, dict[str, str]]:
        """Split ``" <main part> [key=value ...]"`` into its two halves.

        A key may appear at most once per block; a repeated key is a
        ParseError rather than "last one wins".

        Args:
            number: The line number, for errors.
            rest: The text after ``keyword:``.

        Returns:
            The main part and the metadata as a key-to-value dict.

        Raises:
            droneflow.errors.ParseError: If the block or one of its entries
                is malformed, or a key is repeated.
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
