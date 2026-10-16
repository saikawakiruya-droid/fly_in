"""Shared fixtures for the pathfinding tests."""

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
    ) -> Network:
        """Build a network from a compact edge description."""
        ...


def build_network(
    edges: str,
    types: dict[str, ZoneType] | None = None,
    start: str = "s",
    end: str = "g",
    isolated: tuple[str, ...] = (),
) -> Network:
    """Build a network from space separated ``a-b`` edges.

    Zones are registered in order of first appearance (start and end are
    always created, even without connections), and connections in the
    order they are written, which is the declaration order the
    pathfinder must keep. Zones missing from ``types`` are NORMAL.
    """
    zone_types = types or {}
    pairs = [tuple(edge.split("-")) for edge in edges.split()]
    names: list[str] = []
    for name in [start, end, *(n for p in pairs for n in p), *isolated]:
        if name not in names:
            names.append(name)

    network = Network()
    for name in names:
        if name == start:
            role = ZoneRole.START
        elif name == end:
            role = ZoneRole.END
        else:
            role = ZoneRole.HUB
        network.add_zone(
            Zone(
                name=name,
                x=0,
                y=0,
                zone_type=zone_types.get(name, ZoneType.NORMAL),
                role=role,
            )
        )
    for zone_a, zone_b in pairs:
        network.add_connection(Connection(zone_a=zone_a, zone_b=zone_b))
    return network


@pytest.fixture
def make_network() -> NetworkFactory:
    """Return a factory that builds small networks in one line."""
    return build_network


GRID_SIZE = 20


def grid_name(row: int, col: int) -> str:
    """Return the zone name used for one cell of the grid network."""
    return f"c{row}_{col}"


@pytest.fixture
def grid_network() -> Network:
    """Return a GRID_SIZE x GRID_SIZE all-normal grid.

    The start is the top-left cell and the end the bottom-right cell, so
    every cell's distance is its Manhattan distance to the end.
    """
    edges: list[str] = []
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            here = grid_name(row, col)
            if col + 1 < GRID_SIZE:
                edges.append(f"{here}-{grid_name(row, col + 1)}")
            if row + 1 < GRID_SIZE:
                edges.append(f"{here}-{grid_name(row + 1, col)}")
    last = GRID_SIZE - 1
    return build_network(
        " ".join(edges), start=grid_name(0, 0), end=grid_name(last, last)
    )


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
