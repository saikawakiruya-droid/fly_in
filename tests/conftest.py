"""Fixtures shared by every test package.

``make_network`` builds a small network in code, and ``write_map``
writes a map file for end-to-end tests that go through the parser.
"""

from pathlib import Path
from typing import Callable, Protocol

import pytest

from droneflow.models.connection import Connection
from droneflow.models.network import Network
from droneflow.models.zone import Zone, ZoneRole, ZoneType


class NetworkFactory(Protocol):
    """Signature of the ``make_network`` fixture."""

    def __call__(
        self,
        edges: str,
        types: dict[str, ZoneType] | None = None,
        start: str = "s",
        end: str = "g",
        isolated: tuple[str, ...] = (),
        capacity: dict[str, int] | None = None,
        links: dict[str, int] | None = None,
    ) -> Network:
        """Build a network from a compact edge description."""
        ...


def build_network(
    edges: str,
    types: dict[str, ZoneType] | None = None,
    start: str = "s",
    end: str = "g",
    isolated: tuple[str, ...] = (),
    capacity: dict[str, int] | None = None,
    links: dict[str, int] | None = None,
) -> Network:
    """Build a network from space separated ``a-b`` edges.

    Zones are registered in order of first appearance (start and end are
    always created, even without connections), and connections in the
    order they are written, which is the declaration order the
    pathfinder must keep and the name a connection is printed with.

    Args:
        edges: Connections such as ``"s-a a-g"``.
        types: Zone types by name; zones missing here are NORMAL.
        start: Name of the start zone.
        end: Name of the end zone.
        isolated: Extra zones with no connection.
        capacity: ``max_drones`` of hubs by name; hubs missing here get 1,
            the parser's default. Start and end always get None, as the
            parser normalizes them.
        links: ``max_link_capacity`` by connection name (``"s-a"``, as
            written in ``edges``); connections missing here get 1.
    """
    zone_types = types or {}
    zone_capacity = capacity or {}
    link_capacity = links or {}
    pairs = [tuple(edge.split("-")) for edge in edges.split()]
    names: list[str] = []
    for name in [start, end, *(n for p in pairs for n in p), *isolated]:
        if name not in names:
            names.append(name)

    network = Network()
    for name in names:
        max_drones: int | None = None
        if name == start:
            role = ZoneRole.START
        elif name == end:
            role = ZoneRole.END
        else:
            role = ZoneRole.HUB
            max_drones = zone_capacity.get(name, 1)
        network.add_zone(
            Zone(
                name=name,
                x=0,
                y=0,
                zone_type=zone_types.get(name, ZoneType.NORMAL),
                role=role,
                max_drones=max_drones,
            )
        )
    for zone_a, zone_b in pairs:
        network.add_connection(
            Connection(
                zone_a=zone_a,
                zone_b=zone_b,
                max_link_capacity=link_capacity.get(f"{zone_a}-{zone_b}", 1),
            )
        )
    return network


@pytest.fixture
def make_network() -> NetworkFactory:
    """Return a factory that builds small networks in one line."""
    return build_network


@pytest.fixture
def write_map(tmp_path: Path) -> Callable[[str], Path]:
    """Return a function writing a map file under tmp_path.

    The map text must start with ``nb_drones: <n>`` on its physical first
    line (decisions 2026-10-16).
    """

    def write(text: str) -> Path:
        path = tmp_path / "map.txt"
        path.write_text(text)
        return path

    return write
