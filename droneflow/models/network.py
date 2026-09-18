"""Network: the hand-built graph of zones and connections (no graph libs)."""

from ..errors import SimulationError, ZoneNotFoundError
from .connection import Connection
from .zone import Zone, ZoneRole


class Network:
    """Holds all zones and connections and exposes adjacency lookups."""

    def __init__(self) -> None:
        self.zones: dict[str, Zone] = {}
        self.connections: list[Connection] = []
        self._adjacency: dict[str, list[Connection]] = {}

    def add_zone(self, zone: Zone) -> None:
        """Register a new zone in the network.

        Does not check for duplicate names; the caller (the parser) is
        responsible for enforcing that constraint.
        """
        self.zones[zone.name] = zone

    def add_connection(self, connection: Connection) -> None:
        """Register a new connection and update adjacency for both ends.

        Does not check for duplicate connections; the caller (the parser)
        is responsible for enforcing that constraint.
        """
        self.connections.append(connection)
        self._adjacency.setdefault(connection.zone_a, []).append(connection)
        self._adjacency.setdefault(connection.zone_b, []).append(connection)

    def get_zone(self, name: str) -> Zone:
        """Look up a zone by name.

        Raises:
            ZoneNotFoundError: If no zone with this name is registered.
        """
        try:
            return self.zones[name]
        except KeyError:
            raise ZoneNotFoundError(name) from None

    def neighbors(self, name: str) -> list[Connection]:
        """Return all connections incident to the given zone."""
        return self._adjacency.get(name, [])

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
        matches = [zone for zone in self.zones.values() if zone.role is role]
        if len(matches) != 1:
            raise SimulationError(
                f"expected exactly one zone with role {role!r}, "
                f"found {len(matches)}"
            )
        return matches[0]
