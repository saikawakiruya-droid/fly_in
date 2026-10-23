"""Tests for droneflow.visualization.graphical_view (matplotlib window).

matplotlib runs on its Agg backend (set in ``conftest.py``), which draws
without a display. ``MapScene`` is drawn on a plain ``Figure``. A real
window cannot be opened under Agg, so the window tests either expect
that error or let the Agg canvas pass for an interactive one.
"""

from collections.abc import Callable
from pathlib import Path

import matplotlib.pyplot as plt
import numpy
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import PatchCollection
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from matplotlib.patches import Circle, RegularPolygon

import fly_in
from droneflow.errors import VisualizationError
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.simulation.state import SimulationState
from droneflow.visualization.graphical_view import (
    GraphicalVisualizer,
    MapScene,
    zone_color,
)

CoordNetwork = Callable[..., Network]
WriteMap = Callable[[str], Path]


@pytest.fixture
def network(coord_network: CoordNetwork) -> Network:
    """Return ``s - r - g`` in a row, r restricted, plus s-g over r."""
    return coord_network(
        [("s", 0, 0), ("r", 2, 0), ("g", 4, 0)], "s-r r-g s-g",
        types={"r": ZoneType.RESTRICTED},
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


def test_connection_in_use_is_drawn_lighter(network: Network) -> None:
    """VG10: only the connection a drone flies along gets the busy color."""
    scene = scene_of(network)
    state = SimulationState(network, 1)
    state.enter_transit(1, network.connections[0], "r")

    scene.show(state)

    colors = numpy.asarray(scene.lines.get_colors()).tolist()
    assert colors[0] == pytest.approx(to_rgba("#96a0b9"))
    assert colors[1] == pytest.approx(to_rgba("#555c6c"))
    assert colors[2] == pytest.approx(to_rgba("#555c6c"))


def test_zone_color_falls_back_to_matplotlib_then_gray() -> None:
    """VG06: palette names, then matplotlib names, then a neutral gray."""
    assert zone_color("red") == pytest.approx((220 / 255, 40 / 255, 40 / 255))
    assert zone_color("Chocolate") == pytest.approx(
        (210 / 255, 105 / 255, 30 / 255)
    )
    assert zone_color("rainbow") == zone_color(None)


def test_no_window_under_agg(network: Network) -> None:
    """VG07: without an interactive backend the view cannot open."""
    with pytest.raises(VisualizationError, match="no display"):
        GraphicalVisualizer(network)
    assert plt.get_fignums() == []


def test_main_reports_no_display_in_one_line(
    write_map: WriteMap, subject_map: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """VG08: --graphical without a display: exit 1 and one error line."""
    code = fly_in.main([str(write_map(subject_map)), "--graphical"])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err == (
        "error: cannot open the graphical window (no display?)\n"
    )


@pytest.mark.filterwarnings("ignore:FigureCanvasAgg is non-interactive")
def test_closing_the_window_stops_the_drawing(
    network: Network, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VG09: after the window is closed, render draws nothing."""
    monkeypatch.setattr(FigureCanvasAgg, "required_interactive_framework",
                        "tk")
    view = GraphicalVisualizer(network, delay=0)
    state = SimulationState(network, 1)
    view.begin(state)

    plt.close(view.figure)
    state.turn_number = 1
    view.render(state, [])
    view.close()

    assert not view.is_open
    assert view.scene.axes.get_title(loc="left").startswith("Turn 0")
