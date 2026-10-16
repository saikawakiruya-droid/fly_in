"""Rules that need to see more than one line of the map at a time.

Each rule inspects a newly built entry against the Network assembled so far
and raises ValueError when the entry would break a parser constraint.
"""

from abc import ABC, abstractmethod
from typing import Protocol

from ..models.connection import Connection
from ..models.network import Network
from ..models.zone import Zone, ZoneRole
from .map_format import Entry


class Rule(Protocol):
    """Anything that can veto an entry given the network built so far."""

    def check(self, entry: Entry, network: Network) -> None:
        """Raise ValueError if ``entry`` violates this rule."""


class ZoneRule(ABC):
    """A rule about zones; entries of any other kind are ignored."""

    def check(self, entry: Entry, network: Network) -> None:
        if isinstance(entry, Zone):
            self.check_zone(entry, network)

    @abstractmethod
    def check_zone(self, zone: Zone, network: Network) -> None:
        """Raise ValueError if ``zone`` violates this rule."""


class ConnectionRule(ABC):
    """A rule about connections; entries of any other kind are ignored."""

    def check(self, entry: Entry, network: Network) -> None:
        if isinstance(entry, Connection):
            self.check_connection(entry, network)

    @abstractmethod
    def check_connection(
        self, connection: Connection, network: Network
    ) -> None:
        """Raise ValueError if ``connection`` violates this rule."""


class UniqueZoneName(ZoneRule):
    """A zone name may be declared only once."""

    def check_zone(self, zone: Zone, network: Network) -> None:
        if zone.name in network.zones:
            raise ValueError(f"duplicate zone name: {zone.name}")


class SingleStartAndEnd(ZoneRule):
    """At most one start_hub and one end_hub may be declared."""

    def check_zone(self, zone: Zone, network: Network) -> None:
        if zone.role is ZoneRole.HUB:
            return
        if any(other.role is zone.role for other in network.zones.values()):
            raise ValueError(f"duplicate {zone.role.value}")


class KnownEndpoints(ConnectionRule):
    """A connection may only join zones that were already declared."""

    def check_connection(
        self, connection: Connection, network: Network
    ) -> None:
        for name in (connection.zone_a, connection.zone_b):
            if name not in network.zones:
                raise ValueError(f"unknown zone: {name}")


class UniqueConnection(ConnectionRule):
    """a-b and b-a are the same connection and may be declared only once."""

    def check_connection(
        self, connection: Connection, network: Network
    ) -> None:
        if any(
            existing.other_end(connection.zone_a) == connection.zone_b
            for existing in network.neighbors(connection.zone_a)
        ):
            raise ValueError(
                f"duplicate connection: "
                f"{connection.zone_a}-{connection.zone_b}"
            )


def default_rules() -> list[Rule]:
    """Return the rules enforcing the parser constraints."""
    return [
        UniqueZoneName(),
        SingleStartAndEnd(),
        KnownEndpoints(),
        UniqueConnection(),
    ]
