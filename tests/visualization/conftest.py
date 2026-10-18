"""Fixtures for the visualization tests (none of them need pygame).

``coord_network`` registers zones with coordinates and colors, which
``make_network`` leaves at (0, 0) and unset. ``tty_stream`` (a terminal
stand-in) comes from ``tests/conftest.py``. The graphical view's headless
fixture lives in its own test file, which is skipped as a whole without
pygame.
"""

from typing import Protocol

import pytest

from droneflow.models.connection import Connection
from droneflow.models.network import Network
from droneflow.models.zone import Zone, ZoneRole, ZoneType

ZoneSpec = tuple[str, int, int]


class CoordNetworkFactory(Protocol):
    """Signature of the ``coord_network`` fixture."""

    def __call__(
        self,
        zones: list[ZoneSpec],
        edges: str = "",
        colors: dict[str, str] | None = None,
        types: dict[str, ZoneType] | None = None,
    ) -> Network:
        """Build a network with zone coordinates."""
        ...


def build_coord_network(
    zones: list[ZoneSpec],
    edges: str = "",
    colors: dict[str, str] | None = None,
    types: dict[str, ZoneType] | None = None,
) -> Network:
    """Build a network from ``(name, x, y)`` triples and ``a-b`` edges.

    The first zone is the start and the last one the end (both without a
    capacity, as the parser makes them); the others are hubs holding one
    drone. Zones missing from ``colors`` have no color and zones missing
    from ``types`` are NORMAL. Every connection holds one drone.
    """
    zone_colors = colors or {}
    zone_types = types or {}
    network = Network()
    for index, (name, x, y) in enumerate(zones):
        role = ZoneRole.HUB
        if index == 0:
            role = ZoneRole.START
        elif index == len(zones) - 1:
            role = ZoneRole.END
        network.add_zone(
            Zone(
                name=name,
                x=x,
                y=y,
                zone_type=zone_types.get(name, ZoneType.NORMAL),
                role=role,
                color=zone_colors.get(name),
                max_drones=1 if role is ZoneRole.HUB else None,
            )
        )
    for edge in edges.split():
        zone_a, zone_b = edge.split("-")
        network.add_connection(Connection(zone_a, zone_b, 1))
    return network


@pytest.fixture
def coord_network() -> CoordNetworkFactory:
    """Return the ``build_coord_network`` helper."""
    return build_coord_network
