"""Tests for droneflow.visualization.matplotlib_window.view (the window).

A real window cannot be opened under the Agg backend (set in
``conftest.py``), so these tests either expect that error or let the Agg
canvas pass for an interactive one.
"""

from collections.abc import Callable
from pathlib import Path

import matplotlib.pyplot as plt
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

import fly_in
from droneflow.errors import VisualizationError
from droneflow.models.network import Network
from droneflow.simulation.state import SimulationState
from droneflow.visualization.matplotlib_window.view import (
    MatplotlibWindowVisualizer,
)

WriteMap = Callable[[str], Path]


def test_no_window_under_agg(network: Network) -> None:
    """VG07: without an interactive backend the view cannot open."""
    with pytest.raises(VisualizationError, match="no display"):
        MatplotlibWindowVisualizer(network)
    assert plt.get_fignums() == []


def test_main_reports_no_display_in_one_line(
    write_map: WriteMap, subject_map: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """VG08: --matplotlib-window without a display: exit 1, one error."""
    code = fly_in.main([str(write_map(subject_map)), "--matplotlib-window"])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err == (
        "error: cannot open the matplotlib window (no display?)\n"
    )


@pytest.mark.filterwarnings("ignore:FigureCanvasAgg is non-interactive")
def test_closing_the_window_stops_the_drawing(
    network: Network, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VG09: after the window is closed, render draws nothing."""
    monkeypatch.setattr(FigureCanvasAgg, "required_interactive_framework",
                        "tk")
    view = MatplotlibWindowVisualizer(network, delay=0)
    state = SimulationState(network, 1)
    view.begin(state)

    plt.close(view.figure)
    state.turn_number = 1
    view.render(state, [])
    view.close()

    assert not view.is_open
    assert view.scene.axes.get_title(loc="left").startswith("Turn 0")
