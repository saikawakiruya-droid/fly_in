"""Connection (edge) between two zones."""

from dataclasses import dataclass


@dataclass
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

    def involves(self, zone_name: str) -> bool:
        """Return whether the zone is one of this connection's endpoints."""
        return zone_name == self.zone_a or zone_name == self.zone_b

    def other_end(self, zone_name: str) -> str:
        """Return the endpoint opposite the given zone name.

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
