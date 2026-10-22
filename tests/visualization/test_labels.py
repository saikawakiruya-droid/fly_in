"""Tests for droneflow.visualization.labels (no pygame needed).

Widths are measured with ``len`` (one character = one pixel), so the
expected cuts can be counted by hand. Decision 2026-10-22 "fix the
graphical labels"; test design ``2026-10-22_test-design-visual-labels.md``
(VL01-VL14).
"""

from collections.abc import Callable

import pytest

from droneflow.models.network import Network
from droneflow.models.zone import Zone, ZoneRole, ZoneType
from droneflow.simulation.state import SimulationState
from droneflow.visualization.labels import (
    fit_items,
    fit_text,
    load_label,
    zone_title,
)

MakeNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]


def zone(name: str, role: ZoneRole = ZoneRole.HUB) -> Zone:
    """Return a normal zone with the given name and role."""
    return Zone(name, 0, 0, ZoneType.NORMAL, role, max_drones=1)


def test_hub_title() -> None:
    """VL01: a hub's name is shown as it is."""
    assert zone_title(zone("roof1"), len, 20) == "roof1"


def test_start_and_end_titles() -> None:
    """VL02: start and end get their role in parentheses."""
    assert zone_title(zone("s", ZoneRole.START), len, 20) == "s (start)"
    assert zone_title(zone("g", ZoneRole.END), len, 20) == "g (end)"


def test_long_name_keeps_the_role() -> None:
    """VL03: only the name is cut; " (start)" is always shown."""
    title = zone_title(zone("abcdefghij", ZoneRole.START), len, 12)

    assert title == "abc~ (start)"


@pytest.mark.parametrize(
    ("width", "expected"), [(6, "abcdef"), (4, "abc~"), (0, "a~")]
)
def test_fit_text(width: int, expected: str) -> None:
    """VL04: cut with ``~``; one character and the ``~`` always stay."""
    assert fit_text("abcdef", len, width) == expected


def test_occupancy_over_capacity(
    make_network: MakeNetwork, place: Place
) -> None:
    """VL05: a zone with a capacity shows occupancy/capacity."""
    network = make_network("s-a a-g", capacity={"a": 2})
    state = place(network, 1, at={1: "a"})

    assert load_label(state, network.get_zone("a")) == "1/2"


@pytest.fixture
def restricted(make_network: MakeNetwork) -> Network:
    """Return s-r-g with r restricted (capacity 1)."""
    return make_network("s-r r-g", types={"r": ZoneType.RESTRICTED})


def test_arrivals_are_shown_apart(restricted: Network, place: Place) -> None:
    """VL06: one in r and one flying to it reads 1/1 +1, not 2/1."""
    state = place(restricted, 2, at={1: "r"}, flying={2: ("s", "r")})

    assert load_label(state, restricted.get_zone("r")) == "1/1 +1"


def test_only_arrivals(restricted: Network, place: Place) -> None:
    """VL07: an empty zone with a drone flying to it reads 0/1 +1."""
    state = place(restricted, 1, flying={1: ("s", "r")})

    assert load_label(state, restricted.get_zone("r")) == "0/1 +1"


def test_start_and_end_counts(
    make_network: MakeNetwork, place: Place
) -> None:
    """VL08: start shows the drones in it, end the drones delivered."""
    network = make_network("s-g")
    state = place(network, 3, at={1: "g"})

    assert load_label(state, network.get_zone("s")) == "2"
    assert load_label(state, network.get_zone("g")) == "1 in"


def test_blocked_has_no_count(
    make_network: MakeNetwork, place: Place
) -> None:
    """VL09: a blocked zone shows no count at all."""
    network = make_network(
        "s-g", types={"b": ZoneType.BLOCKED}, isolated=("b",)
    )

    assert load_label(place(network, 1), network.get_zone("b")) is None


def test_all_moves_fit() -> None:
    """VL10: moves that fit are all shown, space separated."""
    assert fit_items(["D1-a", "D2-b"], len, 9) == "D1-a D2-b"


def test_moves_cut_with_a_count() -> None:
    """VL11: the moves that do not fit are counted."""
    items = ["D1-a", "D2-b", "D3-c", "D4-d", "D5-e"]

    assert fit_items(items, len, 18) == "D1-a ... +4 more"


def test_no_move_fits() -> None:
    """VL12: the count is shown even if it does not fit itself."""
    assert fit_items(["D1-a", "D2-b", "D3-c"], len, 5) == "... +3 more"


def test_no_moves() -> None:
    """VL13: a turn without moves shows a dash."""
    assert fit_items([], len, 50) == "-"


def test_many_moves_are_measured_few_times() -> None:
    """VL14: thousands of moves need only a few measurements."""
    items = [f"D{n}-z{n}" for n in range(1, 3001)]
    calls: list[str] = []

    def measure(text: str) -> int:
        calls.append(text)
        return len(text)

    text = fit_items(items, measure, 200)

    assert len(text) <= 200
    shown, rest = text.split(" ... +")
    assert len(shown.split()) + int(rest.removesuffix(" more")) == 3000
    assert len(calls) <= 20
