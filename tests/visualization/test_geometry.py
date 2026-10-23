"""Tests for droneflow.visualization.geometry (graphical view layout).

Positions are map units. A connection must stay straight unless its line
would cross a zone drawn with the given radius.
"""

import math

import pytest

from droneflow.visualization.geometry import (
    ARC_SAMPLES,
    CLEARANCE,
    middle,
    route,
    spread_duplicates,
    zone_radius,
)


def test_zone_radius_is_a_share_of_the_closest_gap() -> None:
    """GM01: 0.3 of the closest distinct pair, gaps over 1 counting as 1."""
    assert zone_radius([(0, 0), (4, 0), (4, 0.5), (4, 0.5)]) == (
        pytest.approx(0.15)
    )
    assert zone_radius([(0, 0), (4, 0)]) == pytest.approx(0.3)
    assert zone_radius([(5, 5)]) == pytest.approx(0.3)


def test_shared_positions_are_spread_apart() -> None:
    """GM02: zones at one position move apart; a lone zone stays."""
    spread = spread_duplicates({"a": (0, 0), "b": (0, 0), "c": (9, 9)}, 1.0)

    assert spread["c"] == (9, 9)
    assert math.dist(spread["a"], spread["b"]) >= 2.0


def test_line_stays_straight_beside_a_zone() -> None:
    """GM03: a zone just outside the clearance keeps the line straight."""
    beside = (5.0, CLEARANCE + 0.01)

    assert route((0, 0), (10, 0), [beside], 1.0) == [(0, 0), (10, 0)]


def test_line_bends_round_a_zone_in_its_way() -> None:
    """GM04: a zone on the line gives an arc that clears it."""
    path = route((0, 0), (10, 0), [(5.0, 0.0)], 1.0)

    assert len(path) == ARC_SAMPLES + 1
    assert path[0] == (0, 0) and path[-1] == pytest.approx((10, 0))
    assert min(math.dist(point, (5, 0)) for point in path) >= CLEARANCE
    assert middle(path)[1] > 0  # bends upwards first


def test_connection_to_itself_is_a_loop_above_the_zone() -> None:
    """GM05: a self connection is a closed loop sitting on the zone."""
    path = route((2, 2), (2, 2), [], 1.0)

    assert path[0] == pytest.approx(path[-1])
    assert middle(path)[1] > 2 + 1.0


def test_middle_of_a_straight_line() -> None:
    """GM06: the middle of two points is halfway between them."""
    assert middle([(0, 0), (4, 2)]) == (2, 1)
