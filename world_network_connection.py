"""Connection (edge) between two zones."""

from dataclasses import dataclass


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
