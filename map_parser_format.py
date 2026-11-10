"""The map format as tables: the line kinds and the rules across lines.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* MapFormat: a declarative description of every line a map file may hold.
* Rule: the checks that need to see more than one line of the map.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, TypeVar

from world import Connection, Network, Zone, ZoneRole, ZoneType


# --- MapFormat --------------------------------------------------------
# The table at the bottom of this module is the single place that says which
# keywords exist, what each one carries, and which defaults apply. The
# tokenizer reads it to learn a line's shape; the validator asks each
# LineSpec to turn a tokenized line into a model object.

T = TypeVar("T")

Converter = Callable[[str], object]
"""Turns one raw string into a typed value, or raises ValueError."""


@dataclass(frozen=True)
class DroneCount:
    """The value declared by the ``nb_drones:`` header line."""

    value: int


Entry = Zone | Connection | DroneCount


def to_int(raw: str) -> int:
    """Convert to an integer.

    Args:
        raw: The raw string from the map line.

    Returns:
        The integer value.

    Raises:
        ValueError: If ``raw`` is not an integer.
    """
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"must be an integer, got {raw!r}") from None


def to_positive_int(raw: str) -> int:
    """Convert to an integer greater than zero.

    Args:
        raw: The raw string from the map line.

    Returns:
        The positive integer value.

    Raises:
        ValueError: If ``raw`` is not an integer, or is zero or less.
    """
    value = to_int(raw)
    if value <= 0:
        raise ValueError(f"must be a positive integer, got {value}")
    return value


def to_zone_name(raw: str) -> str:
    """Accept a zone name; dashes are reserved for connection syntax.

    Args:
        raw: The raw string from the map line.

    Returns:
        ``raw`` unchanged.

    Raises:
        ValueError: If ``raw`` contains a dash.
    """
    if "-" in raw:
        raise ValueError(f"must not contain '-', got {raw!r}")
    return raw


def to_zone_type(raw: str) -> ZoneType:
    """Convert to one of the four zone types.

    Args:
        raw: The raw string from the map line.

    Returns:
        The matching ZoneType.

    Raises:
        ValueError: If ``raw`` is not a zone type's value.
    """
    try:
        return ZoneType(raw)
    except ValueError:
        allowed = ", ".join(zone_type.value for zone_type in ZoneType)
        raise ValueError(f"must be one of {allowed}, got {raw!r}") from None


def to_text(raw: str) -> str:
    """Accept the raw string as is, for free-text values such as ``color=``.

    Every FieldSpec needs a converter. Color names are not checked by the
    parser: each view decides what to do with a name it does not know (see
    ``terminal_view.rgb`` and ``matplotlib_window._zone_color``).

    Args:
        raw: The raw string from the map line.

    Returns:
        ``raw`` unchanged.
    """
    return raw


@dataclass(frozen=True)
class Endpoints:
    """The two zone names of a ``connection:`` line."""

    zone_a: str
    zone_b: str


def to_endpoints(raw: str) -> Endpoints:
    """Split ``<name1>-<name2>`` into its two zone names.

    Args:
        raw: The raw string from the map line.

    Returns:
        The two zone names.

    Raises:
        ValueError: If ``raw`` is not two non-empty names joined by one dash.
    """
    parts = raw.split("-")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"must look like <name1>-<name2>, got {raw!r}")
    return Endpoints(parts[0], parts[1])


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
    default: object = None

    def read(self, raw: str | None) -> object:
        """Convert ``raw``, or return the default when it is absent.

        Args:
            raw: The raw string, or None if the field is absent.

        Returns:
            The converted value, or the default.

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
    value: object


class FieldValues:
    """The converted values of one line, read back with their types.

    Values are stored as ``object``; a builder asks for each one with the
    type it expects, and a mismatch (a field spec and its builder that do
    not agree) is reported as a ``TypeError``, a programming error rather
    than a map error.
    """

    def __init__(self, values: Mapping[str, object]) -> None:
        """Keep the values by field name.

        Args:
            values: The converted values, by field name.
        """
        self._values = dict(values)

    def get(self, name: str, kind: type[T]) -> T:
        """Return the value of ``name``, which must be a ``kind``.

        Args:
            name: The field name.
            kind: The type the value must have.

        Returns:
            The value.

        Raises:
            TypeError: If the value is missing or of another type.
        """
        value = self._values.get(name)
        if not isinstance(value, kind):
            raise TypeError(
                f"field {name!r} is {type(value).__name__}, "
                f"not {kind.__name__}"
            )
        return value

    def get_optional(self, name: str, kind: type[T]) -> T | None:
        """Return the value of ``name`` (a ``kind``), or None if unset.

        Args:
            name: The field name.
            kind: The type the value must have when set.

        Returns:
            The value, or None.

        Raises:
            TypeError: If the value is set but of another type.
        """
        if self._values.get(name) is None:
            return None
        return self.get(name, kind)


Builder = Callable[[FieldValues], Entry]


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
    def metadata_keys(self) -> frozenset[str]:
        """Return the metadata keys this kind of line accepts."""
        return frozenset(field.name for field in self.metadata)

    def build(
        self, positional: Sequence[str], metadata: Mapping[str, str]
    ) -> Entry:
        """Convert the raw tokens and build the model object.

        Args:
            positional: The required tokens, in order.
            metadata: The ``key=value`` pairs from the bracketed block.

        Returns:
            The Zone, Connection or DroneCount the line declares.

        Raises:
            ValueError: If any field fails to convert, or a metadata value
                is one this kind of line forbids.
        """
        values: dict[str, object] = {}
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
        return self.builder(FieldValues(values))


class ZoneBuilder:
    """Builds a Zone with a fixed role from converted field values."""

    def __init__(self, role: ZoneRole) -> None:
        """Build zones with this role.

        Args:
            role: The role of every zone this builder makes.
        """
        self._role = role

    def __call__(self, values: FieldValues) -> Zone:
        """Build the Zone; start_hub / end_hub ignore ``max_drones``.

        Args:
            values: The converted fields of a zone line.

        Returns:
            The zone, with this builder's role.
        """
        is_hub = self._role is ZoneRole.HUB
        return Zone(
            name=values.get("name", str),
            x=values.get("x", int),
            y=values.get("y", int),
            zone_type=values.get("zone", ZoneType),
            role=self._role,
            color=values.get_optional("color", str),
            max_drones=values.get("max_drones", int) if is_hub else None,
        )


def build_connection(values: FieldValues) -> Connection:
    """Build a Connection from converted field values.

    Args:
        values: The converted fields of a ``connection:`` line.

    Returns:
        The connection.
    """
    endpoints = values.get("endpoints", Endpoints)
    return Connection(
        endpoints.zone_a,
        endpoints.zone_b,
        values.get("max_link_capacity", int),
    )


def build_drone_count(values: FieldValues) -> DroneCount:
    """Build a DroneCount from converted field values.

    Args:
        values: The converted fields of the ``nb_drones:`` line.

    Returns:
        The declared drone count.
    """
    return DroneCount(values.get("n", int))


class MapFormat:
    """The complete set of line kinds a map file may contain."""

    def __init__(self, header: LineSpec, body: Sequence[LineSpec]) -> None:
        """Keep the first line's spec and the specs of the other lines.

        Args:
            header: The spec of the first line.
            body: The specs of the lines after it.
        """
        self.header = header
        self._body = {spec.keyword: spec for spec in body}

    def find(self, keyword: str) -> LineSpec | None:
        """Return the spec for a body line keyword, or None if unknown.

        Args:
            keyword: The word before the colon.

        Returns:
            The matching spec, or None.
        """
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
    """Return the spec of a zone line (start_hub, end_hub or hub).

    Args:
        keyword: The word before the colon.
        role: The role of the zones this line declares.
        forbidden: Metadata values this kind of line rejects.

    Returns:
        The line's spec.
    """
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


# --- Rule -------------------------------------------------------------
# Each rule inspects a newly built entry against the Network assembled so far
# and raises ValueError when the entry would break a parser constraint.

class Rule(Protocol):
    """Anything that can veto an entry given the network built so far."""

    def check(self, entry: Entry, network: Network) -> None:
        """Raise ValueError if ``entry`` violates this rule.

        Args:
            entry: The entry built from the current line.
            network: The network built from the lines so far.

        Raises:
            ValueError: If the entry breaks the rule.
        """


class ZoneRule(ABC):
    """A rule about zones; entries of any other kind are ignored."""

    def check(self, entry: Entry, network: Network) -> None:
        """Check ``entry`` if it is a Zone.

        Args:
            entry: The entry built from the current line.
            network: The network built from the lines so far.
        """
        if isinstance(entry, Zone):
            self.check_zone(entry, network)

    @abstractmethod
    def check_zone(self, zone: Zone, network: Network) -> None:
        """Raise ValueError if ``zone`` violates this rule.

        Args:
            zone: The zone the current line declares.
            network: The network built from the lines so far.

        Raises:
            ValueError: If the zone breaks the rule.
        """


class ConnectionRule(ABC):
    """A rule about connections; entries of any other kind are ignored."""

    def check(self, entry: Entry, network: Network) -> None:
        """Check ``entry`` if it is a Connection.

        Args:
            entry: The entry built from the current line.
            network: The network built from the lines so far.
        """
        if isinstance(entry, Connection):
            self.check_connection(entry, network)

    @abstractmethod
    def check_connection(
        self, connection: Connection, network: Network
    ) -> None:
        """Raise ValueError if ``connection`` violates this rule.

        Args:
            connection: The connection the current line declares.
            network: The network built from the lines so far.

        Raises:
            ValueError: If the connection breaks the rule.
        """


class UniqueZoneName(ZoneRule):
    """A zone name may be declared only once."""

    def check_zone(self, zone: Zone, network: Network) -> None:
        """Reject a zone whose name is already declared.

        Args:
            zone: The zone the current line declares.
            network: The network built from the lines so far.

        Raises:
            ValueError: If the name is already used.
        """
        if zone.name in network.zones:
            raise ValueError(f"duplicate zone name: {zone.name}")


class SingleStartAndEnd(ZoneRule):
    """At most one start_hub and one end_hub may be declared."""

    def check_zone(self, zone: Zone, network: Network) -> None:
        """Reject a second start_hub or end_hub.

        Args:
            zone: The zone the current line declares.
            network: The network built from the lines so far.

        Raises:
            ValueError: If a zone with the same role is already declared.
        """
        if zone.role is ZoneRole.HUB:
            return
        if any(other.role is zone.role for other in network.zones.values()):
            raise ValueError(f"duplicate {zone.role.value}")


class KnownEndpoints(ConnectionRule):
    """A connection may only join zones that were already declared."""

    def check_connection(
        self, connection: Connection, network: Network
    ) -> None:
        """Reject a connection to a zone not declared yet.

        Args:
            connection: The connection the current line declares.
            network: The network built from the lines so far.

        Raises:
            ValueError: If either zone is not declared yet.
        """
        for name in (connection.zone_a, connection.zone_b):
            if name not in network.zones:
                raise ValueError(f"unknown zone: {name}")


class DistinctEndpoints(ConnectionRule):
    """A connection joins two different zones (``a-a`` is not allowed)."""

    def check_connection(
        self, connection: Connection, network: Network
    ) -> None:
        """Reject a connection from a zone to itself.

        Args:
            connection: The connection the current line declares.
            network: The network built from the lines so far.

        Raises:
            ValueError: If both ends are the same zone.
        """
        if connection.zone_a == connection.zone_b:
            raise ValueError(
                "a connection must join two different zones, got "
                f"{connection.zone_a}-{connection.zone_b}"
            )


class UniqueConnection(ConnectionRule):
    """a-b and b-a are the same connection and may be declared only once."""

    def check_connection(
        self, connection: Connection, network: Network
    ) -> None:
        """Reject a connection between two already-connected zones.

        Args:
            connection: The connection the current line declares.
            network: The network built from the lines so far.

        Raises:
            ValueError: If the two zones are already connected.
        """
        if network.connection_between(
            connection.zone_a, connection.zone_b
        ) is not None:
            raise ValueError(
                f"duplicate connection: "
                f"{connection.zone_a}-{connection.zone_b}"
            )


def default_rules() -> list[Rule]:
    """Return the rules enforcing the parser constraints.

    Returns:
        A new list of the rules, in the order they are checked.
    """
    return [
        UniqueZoneName(),
        SingleStartAndEnd(),
        KnownEndpoints(),
        DistinctEndpoints(),
        UniqueConnection(),
    ]
