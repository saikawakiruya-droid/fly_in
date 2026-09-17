"""Zone and zone-type definitions."""

from dataclasses import dataclass
from enum import Enum


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


@dataclass
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
