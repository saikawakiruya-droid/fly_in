"""Fixtures for the matplotlib view tests (scene and window).

matplotlib is already on its Agg backend (``tests/visualization/
conftest.py``), which draws without a display.
"""

from collections.abc import Callable

import pytest

from droneflow.models.network import Network
from droneflow.models.zone import ZoneType

CoordNetwork = Callable[..., Network]


@pytest.fixture
def network(coord_network: CoordNetwork) -> Network:
    """Return ``s - r - g`` in a row, r restricted, plus s-g over r."""
    return coord_network(
        [("s", 0, 0), ("r", 2, 0), ("g", 4, 0)], "s-r r-g s-g",
        types={"r": ZoneType.RESTRICTED},
    )
