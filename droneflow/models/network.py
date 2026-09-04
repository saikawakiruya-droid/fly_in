"""Network: the hand-built graph of zones and connections (no graph libs)."""

from .connection import Connection
from .zone import Zone


class Network:
    """Holds all zones and connections and exposes adjacency lookups."""

    def __init__(self) -> None:
        self.zones: dict[str, Zone] = {}
        self.connections: list[Connection] = []
        self._adjacency: dict[str, list[Connection]] = {}

    def add_zone(self, zone: Zone) -> None:
        """Register a new zone in the network."""
        raise NotImplementedError

    def add_connection(self, connection: Connection) -> None:
        """Register a new connection and update adjacency for both ends."""
        raise NotImplementedError

    def get_zone(self, name: str) -> Zone:
        """Look up a zone by name."""
        raise NotImplementedError

    def neighbors(self, name: str) -> list[Connection]:
        """Return all connections incident to the given zone."""
        raise NotImplementedError

    @property
    def start_zone(self) -> Zone:
        """Return the unique start_hub zone."""
        raise NotImplementedError

    @property
    def end_zone(self) -> Zone:
        """Return the unique end_hub zone."""
        raise NotImplementedError
