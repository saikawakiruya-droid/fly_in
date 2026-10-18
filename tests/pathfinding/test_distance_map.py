"""Tests for droneflow.pathfinding.distance_map."""

import time
from typing import Callable

import pytest

from droneflow.errors import ZoneNotFoundError
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.pathfinding.distance_map import DistanceMap

MakeNetwork = Callable[..., Network]

R = ZoneType.RESTRICTED
P = ZoneType.PRIORITY
X = ZoneType.BLOCKED


def test_distances_on_a_simple_chain(make_network: MakeNetwork) -> None:
    """D01: the end is 0 and each normal step back adds one turn."""
    distances = DistanceMap(make_network("s-a a-g"))
    assert distances.distance("g") == 0
    assert distances.distance("a") == 1
    assert distances.distance("s") == 2


def test_restricted_zone_costs_two_turns_to_enter(
    make_network: MakeNetwork,
) -> None:
    """D02a: the cost is added when entering r, not when leaving it."""
    distances = DistanceMap(make_network("s-r r-g", types={"r": R}))
    assert distances.distance("r") == 1
    assert distances.distance("s") == 3


def test_priority_zone_costs_one_turn_to_enter(
    make_network: MakeNetwork,
) -> None:
    """D02b: a priority zone costs the same as a normal one."""
    distances = DistanceMap(make_network("s-p p-g", types={"p": P}))
    assert distances.distance("p") == 1
    assert distances.distance("s") == 2


def test_restricted_end_counts_its_entry_cost(
    make_network: MakeNetwork,
) -> None:
    """D03: entering a restricted end takes two turns."""
    distances = DistanceMap(make_network("s-a a-g", types={"g": R}))
    assert distances.distance("g") == 0
    assert distances.distance("a") == 2
    assert distances.distance("s") == 3


def test_blocked_zone_has_no_distance_and_is_not_passed_through(
    make_network: MakeNetwork,
) -> None:
    """D04: the shorter route through a blocked zone is not used."""
    distances = DistanceMap(
        make_network("s-x x-g s-a a-b b-g", types={"x": X})
    )
    assert distances.distance("x") is None
    assert distances.distance("s") == 3


def test_dead_ends_get_a_distance_and_isolated_zones_do_not(
    make_network: MakeNetwork,
) -> None:
    """D05: reachable side zones get a distance, unreachable ones None."""
    distances = DistanceMap(make_network("s-a a-g s-d", isolated=("z",)))
    assert distances.distance("s") == 2
    assert distances.distance("d") == 3
    assert distances.distance("z") is None


def test_self_loop_and_cycle_are_handled(make_network: MakeNetwork) -> None:
    """D06: a self loop and a triangle neither hang nor skew distances."""
    distances = DistanceMap(make_network("s-a a-a a-b b-s a-g"))
    assert distances.distance("a") == 1
    assert distances.distance("b") == 2
    assert distances.distance("s") == 2


def test_unknown_zone_name_raises(make_network: MakeNetwork) -> None:
    """D07: an unknown name is an error, not an unreachable zone."""
    distances = DistanceMap(make_network("s-a a-g"))
    with pytest.raises(ZoneNotFoundError) as excinfo:
        distances.distance("nope")
    assert excinfo.value.zone_name == "nope"


def test_blocked_end_leaves_every_zone_without_distance(
    make_network: MakeNetwork,
) -> None:
    """D08: a blocked end is handled without touching its turn cost."""
    network = make_network("s-a a-g", types={"g": X})
    distances = DistanceMap(network)
    for name in network.zones:
        assert distances.distance(name) is None


def test_grid_distances_are_manhattan_distances(
    grid_network: Network,
) -> None:
    """D09: many heap updates on a 20x20 grid still give exact values."""
    began = time.perf_counter()
    distances = DistanceMap(grid_network)
    elapsed = time.perf_counter() - began

    size = 20
    for row in range(size):
        for col in range(size):
            expected = (size - 1 - row) + (size - 1 - col)
            assert distances.distance(f"c{row}_{col}") == expected
    assert distances.distance(grid_network.start_zone.name) == 38
    assert elapsed < 1.0
