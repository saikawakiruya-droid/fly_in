"""MapParser: reads, tokenizes and validates a map file into a World.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* MapReader: yields the lines of a map file together with line numbers.
* LineTokenizer: splits a map line into raw string parts (syntax only).
* MapValidator: turns tokenized lines into a validated World.
* MapParser: turns a map text file into a validated World.
"""

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from errors import ParseError
from map_parser_format import (
    DEFAULT_FORMAT,
    DroneCount,
    Entry,
    LineSpec,
    MapFormat,
    Rule,
    default_rules,
)
from world import Connection, Network, World, Zone, ZoneRole


# --- MapReader --------------------------------------------------------

@dataclass(frozen=True)
class SourceLine:
    """One line of the map file.

    Attributes:
        number: 1-based line number, used in every ParseError.
        text: The line content, without the trailing newline.
    """

    number: int
    text: str


class MapReader:
    """Reads a map file and yields its lines as SourceLine objects.

    The file is read as UTF-8 text. Text mode turns CR LF and CR line
    endings into LF on any system, so only the LF has to be stripped.
    """

    def __init__(self, path: str | Path) -> None:
        """Keep the path of the file to read.

        Args:
            path: The map file.
        """
        self.path = Path(path)

    def __iter__(self) -> Iterator[SourceLine]:
        """Yield every line, numbered from 1, without its line ending.

        Yields:
            Each line of the file, in order.

        Raises:
            OSError: If the file cannot be opened.
            UnicodeDecodeError: If the file is not UTF-8 text.
        """
        with open(self.path, encoding="utf-8") as f:
            for number, text in enumerate(f, start=1):
                yield SourceLine(number, text.rstrip("\n"))


# --- LineTokenizer ----------------------------------------------------

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

    @staticmethod
    def skips(line: SourceLine) -> bool:
        """Return whether the line is blank or a comment.

        Args:
            line: A line of the file.

        Returns:
            True for a blank line or a line starting with ``#``.
        """
        text = line.text.strip()
        return not text or text.startswith("#")

    def tokenize_header(self, line: SourceLine) -> RawLine:
        """Tokenize the mandatory header (``nb_drones: <n>``).

        Args:
            line: The first line of the file that is not blank or a
                comment.

        Returns:
            The header split into its parts.

        Raises:
            errors.ParseError: If the line is not the header, or
                its parts do not match the header's usage.
        """
        spec = self._format.header
        text = line.text.strip()
        keyword, separator, rest = text.partition(":")
        if not separator or keyword != spec.keyword:
            raise ParseError(
                line.number,
                "the first line that is not a comment must be "
                f"'{spec.keyword}: {spec.usage}'",
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
            errors.ParseError: If the keyword is unknown or the
                parts do not match its usage.
        """
        if self.skips(line):
            return None
        text = line.text.strip()
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
            errors.ParseError: If a metadata key is not allowed
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
            errors.ParseError: If the block or one of its entries
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


# --- MapValidator -----------------------------------------------------

class MapValidator:
    """Turns tokenized lines, checked one by one, into a validated World.

    Field conversion belongs to each line's LineSpec; checks that span
    several lines belong to the Rule objects. This class only coordinates.
    """

    def __init__(self, rules: Sequence[Rule]) -> None:
        """Start an empty network checked by ``rules``.

        Args:
            rules: The checks applied to every entry, in order.
        """
        self._rules = list(rules)
        self._network = Network()
        self._nb_drones: int | None = None
        self._last_number = 0

    def accept(self, raw: RawLine) -> None:
        """Validate one tokenized line and record what it declares.

        Args:
            raw: The tokenized line.

        Raises:
            errors.ParseError: If a field is invalid or a rule is
                violated.
        """
        self._last_number = raw.number
        try:
            entry = raw.spec.build(raw.positional, raw.metadata)
            for rule in self._rules:
                rule.check(entry, self._network)
        except ValueError as error:
            raise ParseError(raw.number, str(error)) from None
        self._store(entry)

    def finish(self) -> World:
        """Check what only the whole file can show and return the World.

        Returns:
            The network built so far and the declared drone count.

        Raises:
            errors.ParseError: If the header or a required hub is
                missing.
        """
        if self._nb_drones is None:
            # The first line that is not a comment or blank is always read
            # as the header (anything else there is already an error), so
            # no header means the file has no such line: report line 1.
            raise ParseError(
                1,
                "map file has only comments and blank lines, expected "
                "'nb_drones: <n>'",
            )
        roles = {zone.role for zone in self._network.zones.values()}
        for role in (ZoneRole.START, ZoneRole.END):
            if role not in roles:
                raise ParseError(self._last_number, f"missing {role.value}")
        return World(network=self._network, nb_drones=self._nb_drones)

    def _store(self, entry: Entry) -> None:
        """Record a checked entry: the drone count, a zone or a connection.

        Args:
            entry: The entry built from one line.
        """
        if isinstance(entry, DroneCount):
            self._nb_drones = entry.value
        elif isinstance(entry, Zone):
            self._network.add_zone(entry)
        elif isinstance(entry, Connection):
            self._network.add_connection(entry)


# --- MapParser --------------------------------------------------------

class MapParser:
    """Reads and validates a Fly-in map file, producing a World.

    The work is delegated: MapReader supplies numbered lines, LineTokenizer
    splits them, and MapValidator checks and assembles the result. See the
    subject's Parser Constraints (章VII.4) for the rules being enforced.
    """

    def __init__(self, path: str | Path) -> None:
        """Keep the path of the map file to parse.

        Args:
            path: The map file.
        """
        self.path = Path(path)

    def parse(self) -> World:
        """Parse the map file into a validated World.

        Returns:
            The network and drone count the file declares.

        Raises:
            errors.ParseError: If the file violates any parser
                constraint, including the offending line number and cause.
            OSError: If the file cannot be opened.
            UnicodeDecodeError: If the file is not UTF-8 text.
        """
        tokenizer = LineTokenizer(DEFAULT_FORMAT)
        validator = MapValidator(default_rules())
        header_read = False
        for line in MapReader(self.path):
            if tokenizer.skips(line):
                continue
            if not header_read:
                validator.accept(tokenizer.tokenize_header(line))
                header_read = True
                continue
            raw = tokenizer.tokenize(line)
            if raw is not None:
                validator.accept(raw)
        return validator.finish()
