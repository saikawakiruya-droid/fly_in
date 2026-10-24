"""Tests for droneflow.visualization.matplotlib_window.scene (MapScene).

matplotlib runs on its Agg backend (set in ``conftest.py``), which draws
without a display. ``MapScene`` is drawn on a plain ``Figure``.
"""

import numpy
import pytest
from matplotlib.collections import PatchCollection
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from matplotlib.patches import Circle, RegularPolygon

from droneflow.models.network import Network
from droneflow.simulation.state import SimulationState
from droneflow.visualization.matplotlib_window.scene import (
    MapScene,
    zone_color,
)


def scene_of(network: Network) -> MapScene:
    """Draw the network on a new figure without a window."""
    return MapScene(Figure().add_subplot(), network)


def test_zones_are_drawn_in_map_units(network: Network) -> None:
    """VG01: zones are patches of the routing radius on equal axes."""
    scene = scene_of(network)
    patches = [
        c for c in scene.axes.collections if isinstance(c, PatchCollection)
    ]

    assert scene.axes.get_aspect() == 1.0
    assert scene.radius == pytest.approx(0.3)
    assert len(patches) == 1
    assert len(patches[0].get_paths()) == 3


def test_shape_marks_restricted_zones(network: Network) -> None:
    """VG02: restricted zones are squares, the others circles."""
    scene = scene_of(network)
    zones = network.zones

    assert isinstance(scene._shape(zones["r"]), RegularPolygon)
    circle = scene._shape(zones["s"])
    assert isinstance(circle, Circle)
    assert circle.get_radius() == pytest.approx(scene.radius)


def test_only_the_line_over_a_zone_bends(network: Network) -> None:
    """VG03: s-r and r-g stay straight; s-g goes round r."""
    paths = scene_of(network).paths

    assert len(paths["s-r"]) == 2
    assert len(paths["r-g"]) == 2
    assert len(paths["s-g"]) > 2


def test_show_writes_the_turn_and_groups_drones(network: Network) -> None:
    """VG04: the title has the turn; drones sharing a zone show a count."""
    scene = scene_of(network)
    state = SimulationState(network, 3)
    state.turn_number = 2

    scene.show(state)

    assert scene.axes.get_title(loc="left").startswith("Turn 2")
    assert [t.get_text() for t in scene.axes.texts][-1] == "3"


def test_drone_in_flight_is_drawn_mid_connection(network: Network) -> None:
    """VG05: a drone flying to r is one dot in the middle of s-r."""
    scene = scene_of(network)
    state = SimulationState(network, 1)
    state.enter_transit(1, network.connections[0], "r")

    scene.show(state)

    dots = numpy.asarray(scene.axes.collections[-1].get_offsets())
    assert tuple(dots[0]) == pytest.approx((1.0, 0.0))


def test_connection_in_use_is_highlighted(network: Network) -> None:
    """VG10: only the connection a drone flies along is cyan and thick."""
    scene = scene_of(network)
    state = SimulationState(network, 1)
    state.enter_transit(1, network.connections[0], "r")

    scene.show(state)

    colors = numpy.asarray(scene.lines.get_colors()).tolist()
    widths = numpy.asarray(scene.lines.get_linewidth()).tolist()
    assert colors[0] == pytest.approx(to_rgba("#00dcff"))
    assert colors[1] == pytest.approx(to_rgba("#555c6c"))
    assert colors[2] == pytest.approx(to_rgba("#555c6c"))
    assert widths == pytest.approx([3.0, 1.5, 1.5])

    state.complete_transit(1)
    scene.show(state)

    assert numpy.asarray(scene.lines.get_linewidth()).tolist() == (
        pytest.approx([1.5, 1.5, 1.5])
    )


def test_zone_color_falls_back_to_matplotlib_then_gray() -> None:
    """VG06: palette names, then matplotlib names, then a neutral gray."""
    assert zone_color("red") == pytest.approx((220 / 255, 40 / 255, 40 / 255))
    assert zone_color("Chocolate") == pytest.approx(
        (210 / 255, 105 / 255, 30 / 255)
    )
    assert zone_color("rainbow") == zone_color(None)
