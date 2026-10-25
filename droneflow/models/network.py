"""Network: the hand-built graph of zones and connections (no graph libs)."""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from ..errors import SimulationError, ZoneNotFoundError
from .connection import Connection
from .zone import Zone, ZoneRole


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
