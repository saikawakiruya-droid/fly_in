"""Rules that need to see more than one line of the map at a time.

Each rule inspects a newly built entry against the Network assembled so far
and raises ValueError when the entry would break a parser constraint.
"""

from typing import Protocol

from ..models.connection import Connection
from ..models.network import Network
from ..models.zone import Zone, ZoneRole
from .map_format import Entry


class Rule(Protocol):
    """Anything that can veto an entry given the network built so far."""

    def check(self, entry: Entry, network: Network) -> None:
        """Raise ValueError if ``entry`` violates this rule."""


class UniqueZoneName:
    """A zone name may be declared only once."""

    def check(self, entry: Entry, network: Network) -> None:
        if isinstance(entry, Zone) and entry.name in network.zones:
            raise ValueError(f"duplicate zone name: {entry.name}")


class SingleStartAndEnd:
    """At most one start_hub and one end_hub may be declared."""

    def check(self, entry: Entry, network: Network) -> None:
        if not isinstance(entry, Zone) or entry.role is ZoneRole.HUB:
            return
        if any(zone.role is entry.role for zone in network.zones.values()):
            raise ValueError(f"duplicate {entry.role.value}")


class KnownEndpoints:
    """A connection may only join zones that were already declared."""

    def check(self, entry: Entry, network: Network) -> None:
        if not isinstance(entry, Connection):
            return
        for name in (entry.zone_a, entry.zone_b):
            if name not in network.zones:
                raise ValueError(f"unknown zone: {name}")


class UniqueConnection:
    """a-b and b-a are the same connection and may be declared only once."""

    def check(self, entry: Entry, network: Network) -> None:
        if not isinstance(entry, Connection):
            return
        if any(
            existing.other_end(entry.zone_a) == entry.zone_b
            for existing in network.neighbors(entry.zone_a)
        ):
            raise ValueError(
                f"duplicate connection: {entry.zone_a}-{entry.zone_b}"
            )


def default_rules() -> list[Rule]:
    """Return the rules enforcing the parser constraints."""
    return [
        UniqueZoneName(),
        SingleStartAndEnd(),
        KnownEndpoints(),
        UniqueConnection(),
    ]
