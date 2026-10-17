"""Fixtures for the pathfinding tests.

``make_network`` and ``write_map`` live in ``tests/conftest.py`` and are
shared with the other test packages; only the grid is specific here.
"""

from typing import Callable

import pytest

from droneflow.models.network import Network

GRID_SIZE = 20


def grid_name(row: int, col: int) -> str:
    """Return the zone name used for one cell of the grid network."""
    return f"c{row}_{col}"


@pytest.fixture
def grid_network(make_network: Callable[..., Network]) -> Network:
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
    return make_network(
        " ".join(edges), start=grid_name(0, 0), end=grid_name(last, last)
    )
