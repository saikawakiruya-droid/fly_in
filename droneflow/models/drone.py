"""Drone entity and status tracking."""

from dataclasses import dataclass
from enum import Enum


class DroneStatus(Enum):
    """Lifecycle states of a single drone during the simulation."""

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
        status: Current lifecycle state. The simulation starts every drone
            as AT_ZONE in the start zone.
        in_transit_connection: Name of the connection being traversed, set
            only while status is IN_TRANSIT.
        transit_target: Name of the zone the drone will arrive at, set only
            while status is IN_TRANSIT.
    """

    drone_id: int
    current_zone: str | None
    status: DroneStatus = DroneStatus.AT_ZONE
    in_transit_connection: str | None = None
    transit_target: str | None = None

    @property
    def is_delivered(self) -> bool:
        """Return whether this drone has reached the end zone."""
        return self.status is DroneStatus.DELIVERED
