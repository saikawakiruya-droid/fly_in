"""MapFormat: a declarative description of every line a map file may hold.

The table at the bottom of this module is the single place that says which
keywords exist, what each one carries, and which defaults apply. The
tokenizer reads it to learn a line's shape; the validator asks each
LineSpec to turn a tokenized line into a model object.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..models.connection import Connection
from ..models.zone import Zone, ZoneRole, ZoneType

Converter = Callable[[str], Any]
"""Turns one raw string into a typed value, or raises ValueError."""


@dataclass(frozen=True)
class DroneCount:
    """The value declared by the ``nb_drones:`` header line."""

    value: int


Entry = Zone | Connection | DroneCount


def to_int(raw: str) -> int:
    """Convert to an integer."""
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"must be an integer, got {raw!r}") from None


def to_positive_int(raw: str) -> int:
    """Convert to an integer greater than zero."""
    value = to_int(raw)
    if value <= 0:
        raise ValueError(f"must be a positive integer, got {value}")
    return value


def to_zone_name(raw: str) -> str:
    """Accept a zone name; dashes are reserved for connection syntax."""
    if "-" in raw:
        raise ValueError(f"must not contain '-', got {raw!r}")
    return raw


def to_zone_type(raw: str) -> ZoneType:
    """Convert to one of the four zone types."""
    try:
        return ZoneType(raw)
    except ValueError:
        allowed = ", ".join(zone_type.value for zone_type in ZoneType)
        raise ValueError(f"must be one of {allowed}, got {raw!r}") from None


def to_text(raw: str) -> str:
    """Accept the raw string as is."""
    return raw


def to_endpoints(raw: str) -> tuple[str, str]:
    """Split ``<name1>-<name2>`` into its two zone names."""
    parts = raw.split("-")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"must look like <name1>-<name2>, got {raw!r}")
    return parts[0], parts[1]


@dataclass(frozen=True)
class FieldSpec:
    """One named value on a line, and how to read it.

    Attributes:
        name: Field name; also the metadata key for optional fields.
        convert: Converter applied to the raw string.
        default: Value used when an optional field is absent.
    """

    name: str
    convert: Converter
    default: Any = None

    def read(self, raw: str | None) -> Any:
        """Convert ``raw``, or return the default when it is absent.

        Raises:
            ValueError: If the conversion fails; the message names the field.
        """
        if raw is None:
            return self.default
        try:
            return self.convert(raw)
        except ValueError as error:
            raise ValueError(f"{self.name} {error}") from None


@dataclass(frozen=True)
class ForbiddenOption:
    """A metadata value that one kind of line must not carry.

    Attributes:
        key: Metadata key, matching a FieldSpec name in ``metadata``.
        value: The forbidden value, compared after conversion.
    """

    key: str
    value: Any


Builder = Callable[[Mapping[str, Any]], Entry]


@dataclass(frozen=True)
class LineSpec:
    """The shape of one kind of line, and how to build its model object.

    Attributes:
        keyword: The word before the colon.
        usage: The expected text after the colon, for error messages.
        positional: Required fields, in the order they appear.
        metadata: Optional ``[key=value]`` fields.
        builder: Builds the model object from the converted field values.
        forbidden: Metadata values this kind of line rejects.
    """

    keyword: str
    usage: str
    positional: Sequence[FieldSpec]
    metadata: Sequence[FieldSpec]
    builder: Builder
    forbidden: Sequence[ForbiddenOption] = ()

    @property
    def metadata_keys(self) -> set[str]:
        """Return the metadata keys this kind of line accepts."""
        return {field.name for field in self.metadata}

    def build(
        self, positional: Sequence[str], metadata: Mapping[str, str]
    ) -> Entry:
        """Convert the raw tokens and build the model object.

        Raises:
            ValueError: If any field fails to convert, or a metadata value
                is one this kind of line forbids.
        """
        values: dict[str, Any] = {}
        for field, raw in zip(self.positional, positional):
            values[field.name] = field.read(raw)
        for field in self.metadata:
            values[field.name] = field.read(metadata.get(field.name))
        for option in self.forbidden:
            if option.key in metadata and values[option.key] == option.value:
                raise ValueError(
                    f"{self.keyword} cannot have "
                    f"{option.key}={metadata[option.key]}"
                )
        return self.builder(values)


class ZoneBuilder:
    """Builds a Zone with a fixed role from converted field values."""

    def __init__(self, role: ZoneRole) -> None:
        """Build zones with this role."""
        self._role = role

    def __call__(self, values: Mapping[str, Any]) -> Zone:
        """Build the Zone; start_hub / end_hub ignore ``max_drones``."""
        is_hub = self._role is ZoneRole.HUB
        return Zone(
            name=values["name"],
            x=values["x"],
            y=values["y"],
            zone_type=values["zone"],
            role=self._role,
            color=values["color"],
            max_drones=values["max_drones"] if is_hub else None,
        )


def build_connection(values: Mapping[str, Any]) -> Connection:
    """Build a Connection from converted field values."""
    zone_a, zone_b = values["endpoints"]
    return Connection(zone_a, zone_b, values["max_link_capacity"])


def build_drone_count(values: Mapping[str, Any]) -> DroneCount:
    """Build a DroneCount from converted field values."""
    return DroneCount(values["n"])


class MapFormat:
    """The complete set of line kinds a map file may contain."""

    def __init__(self, header: LineSpec, body: Sequence[LineSpec]) -> None:
        """Keep the first line's spec and the specs of the other lines."""
        self.header = header
        self._body = {spec.keyword: spec for spec in body}

    def find(self, keyword: str) -> LineSpec | None:
        """Return the spec for a body line keyword, or None if unknown."""
        return self._body.get(keyword)


START_END_FORBIDDEN: tuple[ForbiddenOption, ...] = (
    # A blocked start or end can never be left or reached (VII.3).
    ForbiddenOption("zone", ZoneType.BLOCKED),
)
"""Metadata values that start_hub and end_hub must not carry.

Add an entry here to forbid another option on both lines. max_drones is
deliberately absent: on start/end it is ignored, not an error (VII.4).
"""


def _zone_spec(
    keyword: str,
    role: ZoneRole,
    forbidden: Sequence[ForbiddenOption] = (),
) -> LineSpec:
    return LineSpec(
        keyword=keyword,
        usage="<name> <x> <y>",
        positional=(
            FieldSpec("name", to_zone_name),
            FieldSpec("x", to_int),
            FieldSpec("y", to_int),
        ),
        metadata=(
            FieldSpec("zone", to_zone_type, default=ZoneType.NORMAL),
            FieldSpec("color", to_text),
            FieldSpec("max_drones", to_positive_int, default=1),
        ),
        builder=ZoneBuilder(role),
        forbidden=forbidden,
    )


DEFAULT_FORMAT = MapFormat(
    header=LineSpec(
        keyword="nb_drones",
        usage="<n>",
        positional=(FieldSpec("n", to_positive_int),),
        metadata=(),
        builder=build_drone_count,
    ),
    body=(
        _zone_spec("start_hub", ZoneRole.START, START_END_FORBIDDEN),
        _zone_spec("end_hub", ZoneRole.END, START_END_FORBIDDEN),
        _zone_spec("hub", ZoneRole.HUB),
        LineSpec(
            keyword="connection",
            usage="<name1>-<name2>",
            positional=(FieldSpec("endpoints", to_endpoints),),
            metadata=(FieldSpec("max_link_capacity", to_positive_int, 1),),
            builder=build_connection,
        ),
    ),
)
