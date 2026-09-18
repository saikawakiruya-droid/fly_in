"""MapParser: turns a map text file into a validated World."""

from pathlib import Path

from ..errors import ParseError
from ..models.connection import Connection
from ..models.network import Network
from ..models.world import World
from ..models.zone import Zone, ZoneRole, ZoneType

_ZONE_KEYWORDS = {
    "start_hub": ZoneRole.START,
    "end_hub": ZoneRole.END,
    "hub": ZoneRole.HUB,
}
_ZONE_METADATA_KEYS = {"zone", "color", "max_drones"}
_CONNECTION_METADATA_KEYS = {"max_link_capacity"}


class MapParser:
    """Reads and validates a Fly-in map file, producing a World.

    See the subject's Parser Constraints (章VII.4) for the full validation
    rules this class must enforce.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._network = Network()
        self._nb_drones: int | None = None
        self._connection_pairs: set[frozenset[str]] = set()
        self._start_count = 0
        self._end_count = 0
        self._last_line_number = 0

    def parse(self) -> World:
        """Parse the map file into a validated World.

        Raises:
            droneflow.errors.ParseError: If the file violates any parser
                constraint, including the offending line number and cause.
        """
        with open(self.path, encoding="utf-8") as f:
            for line_number, raw_line in enumerate(f, start=1):
                self._last_line_number = line_number
                self._parse_line(line_number, raw_line.strip())
        self._validate()
        assert self._nb_drones is not None
        return World(network=self._network, nb_drones=self._nb_drones)

    def _parse_line(self, line_number: int, line: str) -> None:
        """Dispatch a single stripped line to the matching handler."""
        if line_number == 1:
            if not line.startswith("nb_drones:"):
                raise ParseError(
                    line_number, "the first line must be 'nb_drones: <n>'"
                )
            self._parse_nb_drones_line(line_number, line)
            return
        if not line or line.startswith("#"):
            return
        if line.startswith("connection:"):
            self._parse_connection_line(line_number, line)
            return
        keyword = line.split(":", 1)[0]
        if keyword in _ZONE_KEYWORDS:
            self._parse_zone_line(line_number, line)
            return
        raise ParseError(line_number, f"unrecognized line: {line!r}")

    def _parse_nb_drones_line(self, line_number: int, line: str) -> None:
        """Parse the mandatory ``nb_drones: <n>`` first line."""
        value = line.split(":", 1)[1].strip()
        nb_drones = self._parse_positive_int(line_number, value, "nb_drones")
        self._nb_drones = nb_drones

    def _parse_zone_line(self, line_number: int, line: str) -> None:
        """Parse a ``start_hub:`` / ``end_hub:`` / ``hub:`` line."""
        keyword, rest = line.split(":", 1)
        role = _ZONE_KEYWORDS[keyword]
        main_part, metadata = self._split_metadata(line_number, rest)
        self._check_known_keys(line_number, metadata, _ZONE_METADATA_KEYS)

        tokens = main_part.split()
        if len(tokens) != 3:
            raise ParseError(
                line_number,
                f"expected '{keyword}: <name> <x> <y>', got {line!r}",
            )
        name, x_raw, y_raw = tokens
        if "-" in name:
            raise ParseError(
                line_number, f"zone name {name!r} must not contain '-'"
            )
        if name in self._network.zones:
            raise ParseError(line_number, f"duplicate zone name: {name}")
        x = self._parse_int(line_number, x_raw, "x coordinate")
        y = self._parse_int(line_number, y_raw, "y coordinate")

        zone_type = self._parse_zone_type(line_number, metadata.get("zone"))
        color = metadata.get("color")
        if role is ZoneRole.HUB:
            raw_max_drones = metadata.get("max_drones")
            if raw_max_drones is None:
                max_drones = 1
            else:
                max_drones = self._parse_positive_int(
                    line_number, raw_max_drones, "max_drones"
                )
        else:
            max_drones = None

        if role is ZoneRole.START:
            if self._start_count >= 1:
                raise ParseError(line_number, "duplicate start_hub")
            self._start_count += 1
        elif role is ZoneRole.END:
            if self._end_count >= 1:
                raise ParseError(line_number, "duplicate end_hub")
            self._end_count += 1

        self._network.add_zone(
            Zone(
                name=name,
                x=x,
                y=y,
                zone_type=zone_type,
                role=role,
                color=color,
                max_drones=max_drones,
            )
        )

    def _parse_connection_line(self, line_number: int, line: str) -> None:
        """Parse a ``connection:`` line."""
        _, rest = line.split(":", 1)
        main_part, metadata = self._split_metadata(line_number, rest)
        self._check_known_keys(
            line_number, metadata, _CONNECTION_METADATA_KEYS
        )

        tokens = main_part.split()
        if len(tokens) != 1 or tokens[0].count("-") != 1:
            raise ParseError(
                line_number,
                f"expected 'connection: <name1>-<name2>', got {line!r}",
            )
        zone_a, zone_b = tokens[0].split("-", 1)
        if not zone_a or not zone_b:
            raise ParseError(
                line_number,
                f"expected 'connection: <name1>-<name2>', got {line!r}",
            )
        for name in (zone_a, zone_b):
            if name not in self._network.zones:
                raise ParseError(line_number, f"unknown zone: {name}")

        pair = frozenset({zone_a, zone_b})
        if pair in self._connection_pairs:
            raise ParseError(
                line_number, f"duplicate connection: {zone_a}-{zone_b}"
            )
        self._connection_pairs.add(pair)

        max_link_capacity = self._parse_optional_positive_int(
            line_number,
            metadata.get("max_link_capacity"),
            "max_link_capacity",
        )
        self._network.add_connection(
            Connection(
                zone_a=zone_a,
                zone_b=zone_b,
                max_link_capacity=(
                    max_link_capacity if max_link_capacity is not None else 1
                ),
            )
        )

    def _split_metadata(
        self, line_number: int, rest: str
    ) -> tuple[str, dict[str, str]]:
        """Split ``" <main part> [key=value ...]"`` into its two halves.

        Raises:
            droneflow.errors.ParseError: If a metadata block is present but
                malformed (unbalanced or misplaced brackets).
        """
        if "[" not in rest and "]" not in rest:
            return rest.strip(), {}
        if rest.count("[") != 1 or rest.count("]") != 1:
            raise ParseError(line_number, "malformed metadata block")
        open_index = rest.index("[")
        close_index = rest.index("]")
        if close_index < open_index or rest[close_index + 1:].strip():
            raise ParseError(line_number, "malformed metadata block")
        main_part = rest[:open_index].strip()
        metadata_raw = rest[open_index + 1:close_index]
        return main_part, self._parse_metadata(line_number, metadata_raw)

    def _parse_metadata(self, line_number: int, raw: str) -> dict[str, str]:
        """Parse a bracketed ``[key=value ...]`` metadata block."""
        metadata: dict[str, str] = {}
        for token in raw.split():
            if token.count("=") != 1:
                raise ParseError(
                    line_number, f"malformed metadata entry: {token!r}"
                )
            key, value = token.split("=", 1)
            if not key or not value:
                raise ParseError(
                    line_number, f"malformed metadata entry: {token!r}"
                )
            metadata[key] = value
        return metadata

    def _check_known_keys(
        self, line_number: int, metadata: dict[str, str], allowed: set[str]
    ) -> None:
        """Reject any metadata key outside the allowed set for this line."""
        unknown = set(metadata) - allowed
        if unknown:
            raise ParseError(
                line_number,
                f"unknown metadata key(s): {', '.join(sorted(unknown))}",
            )

    def _parse_zone_type(
        self, line_number: int, raw: str | None
    ) -> ZoneType:
        """Resolve the ``zone=`` metadata value, defaulting to normal."""
        if raw is None:
            return ZoneType.NORMAL
        try:
            return ZoneType(raw)
        except ValueError:
            raise ParseError(
                line_number, f"unknown zone type: {raw}"
            ) from None

    def _parse_int(self, line_number: int, raw: str, label: str) -> int:
        """Parse a required integer field, raising ParseError on failure."""
        try:
            return int(raw)
        except ValueError:
            raise ParseError(
                line_number, f"{label} must be an integer, got {raw!r}"
            ) from None

    def _parse_positive_int(
        self, line_number: int, raw: str, label: str
    ) -> int:
        """Parse a required positive integer field."""
        value = self._parse_int(line_number, raw, label)
        if value <= 0:
            raise ParseError(
                line_number, f"{label} must be a positive integer, got {value}"
            )
        return value

    def _parse_optional_positive_int(
        self, line_number: int, raw: str | None, label: str
    ) -> int | None:
        """Parse an optional positive integer metadata value."""
        if raw is None:
            return None
        return self._parse_positive_int(line_number, raw, label)

    def _validate(self) -> None:
        """Run whole-file validation once every line has been read.

        Checks that exactly one start_hub and one end_hub were declared.
        Duplicate names and duplicate connections are already rejected as
        soon as the second occurrence is read; this only needs to catch the
        "zero occurrences" case, which requires having read the whole file.
        """
        if self._nb_drones is None:
            raise ParseError(
                self._last_line_number,
                "map file is empty, expected 'nb_drones: <n>' as the first "
                "line",
            )
        if self._start_count != 1:
            raise ParseError(self._last_line_number, "missing start_hub")
        if self._end_count != 1:
            raise ParseError(self._last_line_number, "missing end_hub")
