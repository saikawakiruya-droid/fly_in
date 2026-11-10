"""The map's model: zones, connections, the network and the world.

The parts, in the order they are defined (each uses the ones above
it; the last one is what the rest of the program uses):

* Zone, ZoneType, ZoneRole: a zone of the map.
* Connection: the edge between two zones.
* Network: the hand-built graph of zones and connections (no graph libs).
* World: the fully parsed, ready-to-simulate map.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from errors import SimulationError, ZoneNotFoundError


# --- Zone -------------------------------------------------------------

class ZoneType(Enum):
    """The four zone types a hub can declare via ``zone=`` metadata."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @property
    def turn_cost(self) -> int:
        """Return the number of turns required to move into this zone type.

        Raises:
            ValueError: If called on BLOCKED, which has no turn cost.
                Callers must check ``is_traversable`` first.
        """
        if self is ZoneType.BLOCKED:
            raise ValueError("blocked zones have no turn cost")
        if self is ZoneType.RESTRICTED:
            return 2
        return 1

    @property
    def is_traversable(self) -> bool:
        """Return whether a drone may ever enter a zone of this type."""
        return self is not ZoneType.BLOCKED


class ZoneRole(Enum):
    """The role a zone plays in the network, independent of its zone type."""

    HUB = "hub"
    START = "start_hub"
    END = "end_hub"


@dataclass(frozen=True)
class Zone:
    """A single zone (node) in the drone network.

    Attributes:
        name: Unique zone identifier (no dashes or spaces).
        x: X coordinate.
        y: Y coordinate.
        zone_type: One of NORMAL, BLOCKED, RESTRICTED, PRIORITY.
        role: Whether this zone is the start, the end, or a regular hub.
        color: Optional display color, for visualization only.
        max_drones: Maximum simultaneous occupants, or None if unlimited
            (always the case for the start and end zones).
    """

    name: str
    x: int
    y: int
    zone_type: ZoneType
    role: ZoneRole
    color: str | None = None
    max_drones: int | None = None

    @property
    def has_unlimited_capacity(self) -> bool:
        """Return True for the start and end zones, which ignore max_drones."""
        return self.role in (ZoneRole.START, ZoneRole.END)

    @property
    def capacity(self) -> int | None:
        """Return how many drones the zone may hold, or None if unlimited.

        The start and end zones are unlimited; so is a hub built without
        ``max_drones`` (the parser always gives hubs one).
        """
        if self.has_unlimited_capacity:
            return None
        return self.max_drones

    def arrival_turn(self, depart_turn: int) -> int:
        """Return the turn a drone departing toward this zone enters it.

        A restricted zone takes two turns: the drone spends the departure
        turn on the connection and lands on the next one. Any other zone
        is entered on the departure turn.

        Args:
            depart_turn: The turn the drone leaves its zone.

        Returns:
            ``depart_turn + 1`` for a restricted zone, else
            ``depart_turn``.
        """
        if self.zone_type is ZoneType.RESTRICTED:
            return depart_turn + 1
        return depart_turn


# --- Connection -------------------------------------------------------

@dataclass(frozen=True)
class Connection:
    """A bidirectional link between two zones.

    Attributes:
        zone_a: Name of one endpoint zone.
        zone_b: Name of the other endpoint zone.
        max_link_capacity: Maximum drones that may traverse this connection
            during the same turn.
    """

    zone_a: str
    zone_b: str
    max_link_capacity: int = 1

    @property
    def name(self) -> str:
        """Return the connection's name as declared, ``zone_a-zone_b``.

        This is the ``<connection>`` printed for drones in flight toward a
        restricted zone. Duplicate connections (a-b and b-a) are rejected
        by the parser, so the name is unique within a network.
        """
        return f"{self.zone_a}-{self.zone_b}"

    def involves(self, zone_name: str) -> bool:
        """Return whether the zone is one of this connection's endpoints.

        Args:
            zone_name: The zone to look for.

        Returns:
            True if the zone is ``zone_a`` or ``zone_b``.
        """
        return zone_name == self.zone_a or zone_name == self.zone_b

    def other_end(self, zone_name: str) -> str:
        """Return the endpoint opposite the given zone name.

        Args:
            zone_name: One of this connection's endpoints.

        Returns:
            The other endpoint (the same name for a self-loop).

        Raises:
            ValueError: If zone_name is not one of this connection's
                endpoints.
        """
        if zone_name == self.zone_a:
            return self.zone_b
        if zone_name == self.zone_b:
            return self.zone_a
        raise ValueError(
            f"{zone_name!r} is not an endpoint of this connection"
        )


# --- Network ----------------------------------------------------------

class Network:
    """The graph of zones and connections declared by a map.

    Zones are kept by name, and each zone's connections are indexed for
    neighbor lookups.
    """

    def __init__(self) -> None:
        """Start with no zones and no connections."""
        self._zones: dict[str, Zone] = {}
        self._connections: tuple[Connection, ...] = ()
        self._adjacency: dict[str, tuple[Connection, ...]] = {}

    @property
    def zones(self) -> Mapping[str, Zone]:
        """Return every zone by name, in declaration order (read-only)."""
        return MappingProxyType(self._zones)

    @property
    def connections(self) -> Sequence[Connection]:
        """Return every connection in declaration order (read-only)."""
        return self._connections

    def add_zone(self, zone: Zone) -> None:
        """Register a new zone in the network.

        Does not check for duplicate names; the caller (the parser) is
        responsible for enforcing that constraint.

        Args:
            zone: The zone to add.
        """
        self._zones[zone.name] = zone

    def add_connection(self, connection: Connection) -> None:
        """Register a new connection with both of its zones.

        Does not check for duplicate connections; the caller (the parser)
        is responsible for enforcing that constraint.

        Args:
            connection: The connection to add.
        """
        self._connections += (connection,)
        for zone_name in (connection.zone_a, connection.zone_b):
            linked = self._adjacency.get(zone_name, ())
            self._adjacency[zone_name] = linked + (connection,)

    def get_zone(self, name: str) -> Zone:
        """Look up a zone by name.

        Args:
            name: The zone's name.

        Returns:
            The zone.

        Raises:
            ZoneNotFoundError: If no zone with this name is registered.
        """
        try:
            return self._zones[name]
        except KeyError:
            raise ZoneNotFoundError(name) from None

    def neighbors(self, name: str) -> Sequence[Connection]:
        """Return all connections incident to the given zone (read-only).

        Args:
            name: The zone's name.

        Returns:
            The connections in declaration order; empty for an unknown
            zone.
        """
        return self._adjacency.get(name, ())

    def connection_between(
        self, zone_a: str, zone_b: str
    ) -> Connection | None:
        """Return the connection linking two zones, in either direction.

        Args:
            zone_a: One zone's name.
            zone_b: The other zone's name.

        Returns:
            The connection, or None if the zones are not directly linked.
            Passing the same name twice finds a self-loop, if declared.
        """
        for connection in self.neighbors(zone_a):
            if connection.other_end(zone_a) == zone_b:
                return connection
        return None

    def connection_named(self, zone_name: str, name: str) -> Connection:
        """Return the connection called ``name`` that touches the zone.

        Args:
            zone_name: A zone at one end of the connection.
            name: The connection's name (``<zone_a>-<zone_b>``).

        Returns:
            The connection.

        Raises:
            SimulationError: If the zone has no connection of that name
                (a drone in flight refers to a connection the network
                does not have).
        """
        for connection in self.neighbors(zone_name):
            if connection.name == name:
                return connection
        raise SimulationError(f"unknown connection {name!r}")

    @property
    def start_zone(self) -> Zone:
        """Return the unique start_hub zone.

        Raises:
            SimulationError: If there is not exactly one START zone. In a
                correctly parsed map this can never happen; the parser is
                responsible for enforcing that constraint.
        """
        return self._unique_role_zone(ZoneRole.START)

    @property
    def end_zone(self) -> Zone:
        """Return the unique end_hub zone.

        Raises:
            SimulationError: If there is not exactly one END zone. In a
                correctly parsed map this can never happen; the parser is
                responsible for enforcing that constraint.
        """
        return self._unique_role_zone(ZoneRole.END)

    def _unique_role_zone(self, role: ZoneRole) -> Zone:
        """Return the only zone with the given role.

        Args:
            role: START or END.

        Returns:
            The zone.

        Raises:
            SimulationError: If there is not exactly one such zone.
        """
        matches = [zone for zone in self._zones.values() if zone.role is role]
        if len(matches) != 1:
            raise SimulationError(
                f"expected exactly one zone with role {role!r}, "
                f"found {len(matches)}"
            )
        return matches[0]


# --- World ------------------------------------------------------------

@dataclass(frozen=True)
class World:
    """Bundles everything the parser produces for the rest of the pipeline.

    Attributes:
        network: The parsed zones and connections.
        nb_drones: Number of drones to route, from ``nb_drones:``.
    """

    network: Network
    nb_drones: int
