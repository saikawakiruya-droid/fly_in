"""Drone entity and status tracking."""

from dataclasses import dataclass
from enum import Enum


class DroneStatus(Enum):
    """Lifecycle states of a single drone during the simulation."""

    WAITING = "waiting"
    AT_ZONE = "at_zone"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"


@dataclass
class Drone:
    """A single drone being routed from the start zone to the end zone.

    Attributes:
        drone_id: Unique numeric identifier (rendered as D<drone_id>).
        current_zone: Name of the zone the drone currently occupies, or None
            while mid-transit through a restricted connection.
        status: Current lifecycle state.
        in_transit_connection: Name of the connection being traversed, set
            only while status is IN_TRANSIT.
        turns_remaining: Turns left before arrival, set only while status is
            IN_TRANSIT.
    """

    drone_id: int
    current_zone: str
    status: DroneStatus = DroneStatus.AT_ZONE
    in_transit_connection: str | None = None
    turns_remaining: int = 0

    @property
    def is_delivered(self) -> bool:
        """Return whether this drone has reached the end zone."""
        raise NotImplementedError
