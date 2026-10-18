"""Tests for droneflow.pathfinding.pathfinder."""

from pathlib import Path
from typing import Callable

import pytest

from droneflow.errors import (
    ParseError,
    UnreachableGoalError,
    ZoneNotFoundError,
)
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.parsing.map_parser import MapParser
from droneflow.pathfinding.distance_map import DistanceMap
from droneflow.pathfinding.pathfinder import Hop, Pathfinder, Route

MakeNetwork = Callable[..., Network]
WriteMap = Callable[[str], Path]

R = ZoneType.RESTRICTED
P = ZoneType.PRIORITY
X = ZoneType.BLOCKED

SELF_LOOP_AND_TRIANGLE = "s-a a-a a-b b-s a-g"

SUBJECT_SAMPLE_MAP = """\
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
hub: tunnelB 7 4 [zone=normal color=red]
hub: obstacleX 5 5 [zone=blocked color=gray]
connection: hub-roof1
connection: hub-corridorA
connection: roof1-roof2
connection: roof2-goal
connection: corridorA-tunnelB [max_link_capacity=2]
connection: tunnelB-goal
"""


def hop_names(hops: list[Hop]) -> list[str]:
    """Return the names of the zones the hops lead to, in order."""
    return [hop.zone.name for hop in hops]


def turn_cost(network: Network, name: str) -> int:
    """Return the turns needed to enter the named zone."""
    return network.get_zone(name).zone_type.turn_cost


def assert_route_is_consistent(network: Network, route: Route) -> None:
    """Check a route against the network without fixed expectations.

    The route ends at the end zone, every step follows a real connection,
    no zone repeats, and the total cost is both the sum of entry costs and
    the distance of the first zone.
    """
    zones = route.zones
    assert zones[-1] == network.end_zone.name
    for here, there in zip(zones, zones[1:]):
        assert any(
            c.other_end(here) == there for c in network.neighbors(here)
        )
    assert len(set(zones)) == len(zones)
    assert route.total_cost == sum(turn_cost(network, z) for z in zones[1:])
    assert route.total_cost == Pathfinder(network).distance(zones[0])


# --- construction -----------------------------------------------------


def test_distance_is_delegated_to_the_distance_map(
    make_network: MakeNetwork,
) -> None:
    """P01: Pathfinder.distance matches DistanceMap for every zone."""
    network = make_network("s-a a-g s-r r-g", types={"r": R})
    pathfinder = Pathfinder(network)
    distances = DistanceMap(network)
    for name in network.zones:
        assert pathfinder.distance(name) == distances.distance(name)
    with pytest.raises(ZoneNotFoundError):
        pathfinder.distance("nope")


@pytest.mark.parametrize(
    ("edges", "types"),
    [
        pytest.param("s-a b-g", {}, id="disconnected"),
        pytest.param("s-x x-g", {"x": X}, id="only-route-blocked"),
        pytest.param("", {}, id="no-connections"),
        pytest.param("s-a a-g", {"g": X}, id="blocked-end"),
    ],
)
def test_unreachable_goal_is_detected_at_construction(
    make_network: MakeNetwork, edges: str, types: dict[str, ZoneType]
) -> None:
    """P02: a map whose goal cannot be reached fails right away."""
    network = make_network(edges, types=types)
    with pytest.raises(UnreachableGoalError) as excinfo:
        Pathfinder(network)
    assert excinfo.value.zone_name == "s"
    assert excinfo.value.goal_name == "g"
    assert "line" not in str(excinfo.value)


def test_isolated_zone_does_not_prevent_construction(
    make_network: MakeNetwork,
) -> None:
    """P03: only the start has to reach the goal."""
    pathfinder = Pathfinder(make_network("s-a a-g", isolated=("z",)))
    assert pathfinder.distance("z") is None


# --- next_hops --------------------------------------------------------


def test_hop_carries_the_connection_and_the_entered_zone(
    make_network: MakeNetwork,
) -> None:
    """N01: a hop holds the connection taken and the zone on its far end."""
    network = make_network("s-a g-a")
    pathfinder = Pathfinder(network)

    hops = pathfinder.next_hops("s")
    assert len(hops) == 1
    assert hops[0].connection is network.connections[0]
    assert hops[0].zone is network.get_zone("a")

    from_a = pathfinder.next_hops("a")
    assert hop_names(from_a) == ["g"]
    assert from_a[0].connection is network.connections[1]


def test_restricted_neighbor_with_equal_distance_is_not_a_tie(
    make_network: MakeNetwork,
) -> None:
    """N02: entry cost + distance is compared, not the distance alone."""
    pathfinder = Pathfinder(make_network("s-r r-g s-a a-g", types={"r": R}))
    assert pathfinder.distance("r") == pathfinder.distance("a") == 1
    assert hop_names(pathfinder.next_hops("s")) == ["a"]


def test_restricted_neighbor_with_equal_real_cost_is_kept(
    make_network: MakeNetwork,
) -> None:
    """N03: restricted zones stay candidates when they really tie."""
    pathfinder = Pathfinder(
        make_network("s-r r-g s-a a-b b-g", types={"r": R})
    )
    assert pathfinder.distance("s") == 3
    assert hop_names(pathfinder.next_hops("s")) == ["r", "a"]


@pytest.mark.parametrize(
    ("edges", "expected"),
    [
        pytest.param("s-a a-g s-b b-g", ["a", "b"], id="a-first"),
        pytest.param("s-b b-g s-a a-g", ["b", "a"], id="b-first"),
    ],
)
def test_ties_follow_connection_declaration_order(
    make_network: MakeNetwork, edges: str, expected: list[str]
) -> None:
    """N04: equal hops keep the map's declaration order, not name order."""
    pathfinder = Pathfinder(make_network(edges))
    assert hop_names(pathfinder.next_hops("s")) == expected


def test_priority_neighbor_comes_first_on_a_tie(
    make_network: MakeNetwork,
) -> None:
    """N05: a tying priority zone is moved ahead of a normal one."""
    pathfinder = Pathfinder(make_network("s-a a-g s-p p-g", types={"p": P}))
    assert hop_names(pathfinder.next_hops("s")) == ["p", "a"]


def test_priority_detour_is_not_a_candidate(
    make_network: MakeNetwork,
) -> None:
    """N06: a longer route is never offered just because it is priority."""
    pathfinder = Pathfinder(
        make_network("s-p p-q q-g s-a a-g", types={"p": P, "q": P})
    )
    assert hop_names(pathfinder.next_hops("s")) == ["a"]


def test_priority_sort_is_stable_within_each_group(
    make_network: MakeNetwork,
) -> None:
    """N07: declaration order survives inside priority and normal groups."""
    pathfinder = Pathfinder(
        make_network("s-a a-g s-p p-g s-b b-g s-q q-g", types={"p": P, "q": P})
    )
    assert hop_names(pathfinder.next_hops("s")) == ["p", "q", "a", "b"]


def test_no_hops_from_goal_unreachable_or_blocked_zones(
    make_network: MakeNetwork,
) -> None:
    """N08: the goal and zones without a distance have no next hop."""
    pathfinder = Pathfinder(
        make_network("s-a a-g s-x", types={"x": X}, isolated=("z",))
    )
    assert pathfinder.next_hops("g") == []
    assert pathfinder.next_hops("z") == []
    assert pathfinder.next_hops("x") == []


def test_blocked_neighbor_of_the_goal_is_skipped(
    make_network: MakeNetwork,
) -> None:
    """N09: a blocked zone is never offered, even if declared first."""
    pathfinder = Pathfinder(make_network("s-x x-g s-a a-g", types={"x": X}))
    assert hop_names(pathfinder.next_hops("s")) == ["a"]


def test_next_hops_of_unknown_zone_raises(make_network: MakeNetwork) -> None:
    """N10: an unknown name is an error, not an empty list."""
    pathfinder = Pathfinder(make_network("s-a a-g"))
    with pytest.raises(ZoneNotFoundError):
        pathfinder.next_hops("nope")


@pytest.mark.parametrize("shape", ["self-loop-and-triangle", "grid"])
def test_next_hops_always_go_down_by_their_entry_cost(
    make_network: MakeNetwork, grid_network: Network, shape: str
) -> None:
    """N11: hops never return to the same zone, repeat, or go uphill."""
    if shape == "grid":
        network = grid_network
    else:
        network = make_network(SELF_LOOP_AND_TRIANGLE)
    pathfinder = Pathfinder(network)
    for name in network.zones:
        here = pathfinder.distance(name)
        names = hop_names(pathfinder.next_hops(name))
        assert len(set(names)) == len(names)
        for there in names:
            assert there != name
            distance = pathfinder.distance(there)
            assert distance is not None
            assert turn_cost(network, there) + distance == here


def test_priority_further_ahead_does_not_reorder_ties(
    make_network: MakeNetwork,
) -> None:
    """N12: priority only breaks ties among the immediate next moves.

    Both routes take three turns; the one through ``a`` reaches a
    priority zone one step later, which does not move it ahead of the
    earlier declared ``b`` (decisions 2026-10-16).
    """
    pathfinder = Pathfinder(
        make_network("s-b b-c c-g s-a a-p p-g", types={"p": P})
    )
    assert hop_names(pathfinder.next_hops("s")) == ["b", "a"]
    assert pathfinder.best_route().zones == ["s", "b", "c", "g"]


# --- best_route -------------------------------------------------------


@pytest.mark.parametrize(
    ("edges", "types", "expected"),
    [
        pytest.param("s-a a-g", {}, Route(["s", "a", "g"], 2), id="normal"),
        pytest.param(
            "s-r r-g", {"r": R}, Route(["s", "r", "g"], 3), id="restricted"
        ),
    ],
)
def test_best_route_sums_entry_costs(
    make_network: MakeNetwork,
    edges: str,
    types: dict[str, ZoneType],
    expected: Route,
) -> None:
    """B01: total_cost is the sum of entry costs, not the hop count."""
    pathfinder = Pathfinder(make_network(edges, types=types))
    assert pathfinder.best_route() == expected


def test_best_route_takes_a_tying_priority_zone(
    make_network: MakeNetwork,
) -> None:
    """B02: following the first hop goes through the priority zone."""
    pathfinder = Pathfinder(make_network("s-a a-g s-p p-g", types={"p": P}))
    route = pathfinder.best_route()
    assert route.zones == ["s", "p", "g"]
    assert route.total_cost == 2


def test_best_route_from_a_given_zone(make_network: MakeNetwork) -> None:
    """B03: routes can start mid-way or at the goal; start by default."""
    pathfinder = Pathfinder(
        make_network("s-r r-g s-a a-b b-g", types={"r": R})
    )
    assert pathfinder.best_route("a") == Route(["a", "b", "g"], 2)
    assert pathfinder.best_route("g") == Route(["g"], 0)
    assert pathfinder.best_route().zones[0] == "s"


@pytest.mark.parametrize("from_zone", ["z", "x"])
def test_best_route_from_unreachable_zone_raises(
    make_network: MakeNetwork, from_zone: str
) -> None:
    """B04: asking from a zone that cannot reach the goal fails."""
    pathfinder = Pathfinder(
        make_network("s-a a-g s-x", types={"x": X}, isolated=("z",))
    )
    with pytest.raises(UnreachableGoalError) as excinfo:
        pathfinder.best_route(from_zone)
    assert excinfo.value.zone_name == from_zone
    assert excinfo.value.goal_name == "g"


def test_best_route_from_unknown_zone_raises_zone_not_found(
    make_network: MakeNetwork,
) -> None:
    """B05: an unknown start is ZoneNotFoundError, not unreachable."""
    pathfinder = Pathfinder(make_network("s-a a-g"))
    with pytest.raises(ZoneNotFoundError):
        pathfinder.best_route("nope")


@pytest.mark.parametrize(
    ("edges", "types"),
    [
        pytest.param("s-x x-g s-a a-b b-g", {"x": X}, id="blocked"),
        pytest.param(SELF_LOOP_AND_TRIANGLE, {}, id="self-loop-and-triangle"),
        pytest.param("s-r r-g s-a a-b b-g", {"r": R}, id="restricted-tie"),
        pytest.param(None, {}, id="grid"),
    ],
)
def test_best_route_is_consistent_with_the_network(
    make_network: MakeNetwork,
    grid_network: Network,
    edges: str | None,
    types: dict[str, ZoneType],
) -> None:
    """B06: routes satisfy the general invariants on varied shapes."""
    if edges is None:
        network = grid_network
    else:
        network = make_network(edges, types=types)
    assert_route_is_consistent(network, Pathfinder(network).best_route())


# --- end to end through the parser ------------------------------------


def test_subject_sample_map_end_to_end(write_map: WriteMap) -> None:
    """E01: the subject's example map gives the hand-computed answers."""
    network = MapParser(write_map(SUBJECT_SAMPLE_MAP)).parse().network
    pathfinder = Pathfinder(network)

    expected = {
        "hub": 3,
        "roof1": 2,
        "corridorA": 2,
        "roof2": 1,
        "tunnelB": 1,
        "goal": 0,
        "obstacleX": None,
    }
    for name, distance in expected.items():
        assert pathfinder.distance(name) == distance
    assert hop_names(pathfinder.next_hops("hub")) == ["corridorA"]
    assert pathfinder.best_route() == Route(
        ["hub", "corridorA", "tunnelB", "goal"], 3
    )


def test_unreachable_map_parses_but_pathfinding_fails(
    write_map: WriteMap,
) -> None:
    """E02: reachability is the pathfinder's job, not the parser's."""
    text = (
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: g 1 1\n"
        "hub: a 2 2\n"
        "connection: s-a\n"
    )
    try:
        network = MapParser(write_map(text)).parse().network
    except ParseError as error:  # pragma: no cover - failure path
        pytest.fail(f"parser rejected a reachability problem: {error}")
    with pytest.raises(UnreachableGoalError):
        Pathfinder(network)
