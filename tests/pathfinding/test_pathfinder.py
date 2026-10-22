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
from droneflow.pathfinding.pathfinder import Hop, Pathfinder

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


def first_hop_route(pathfinder: Pathfinder, name: str) -> list[str]:
    """Follow the first shortest hop from ``name`` until the end zone."""
    zones = [name]
    hops = pathfinder.next_hops(name)
    while hops:
        zones.append(hops[0].zone.name)
        hops = pathfinder.next_hops(zones[-1])
    return zones


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
    assert first_hop_route(pathfinder, "s") == ["s", "b", "c", "g"]


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
    assert first_hop_route(pathfinder, "hub") == [
        "hub", "corridorA", "tunnelB", "goal"
    ]
    assert pathfinder.route_cost(pathfinder.next_hops("hub")[0]) == 3


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


# --- detour_hops ------------------------------------------------------

# (member in the archive, number of detour hops over all its zones)
PROVIDED_MAP_DETOURS = [
    ("maps/easy/01_linear_path.txt", 2),
    ("maps/easy/02_simple_fork.txt", 3),
    ("maps/easy/03_basic_capacity.txt", 2),
    ("maps/medium/01_dead_end_trap.txt", 4),
    ("maps/medium/02_circular_loop.txt", 6),
    ("maps/medium/03_priority_puzzle.txt", 7),
    ("maps/hard/01_maze_nightmare.txt", 23),
    ("maps/hard/02_capacity_hell.txt", 22),
    ("maps/hard/03_ultimate_challenge.txt", 40),
    ("maps/challenger/01_the_impossible_dream.txt", 82),
]


def map_id(member: str) -> str:
    """Return a short test id such as ``easy/01_linear_path``."""
    return member.removeprefix("maps/").removesuffix(".txt")


def costed(pathfinder: Pathfinder, hops: list[Hop]) -> list[tuple[str, int]]:
    """Return each hop's zone with its total cost to the end, in order.

    The total cost is the turns to enter the zone plus its distance.
    """
    result: list[tuple[str, int]] = []
    for hop in hops:
        distance = pathfinder.distance(hop.zone.name)
        assert distance is not None
        result.append((hop.zone.name, hop.zone.zone_type.turn_cost + distance))
    return result


def link_names(hops: list[Hop]) -> list[str]:
    """Return the names of the connections the hops take, in order."""
    return [hop.connection.name for hop in hops]


def square_grid(make_network: MakeNetwork, size: int) -> Network:
    """Return an all-normal ``size`` x ``size`` grid (start top-left).

    Every horizontal connection is declared before the vertical ones.
    """
    edges: list[str] = []
    for row in range(size):
        for col in range(size - 1):
            edges.append(f"c{row}_{col}-c{row}_{col + 1}")
    for row in range(size - 1):
        for col in range(size):
            edges.append(f"c{row}_{col}-c{row + 1}_{col}")
    last = size - 1
    return make_network(" ".join(edges), start="c0_0", end=f"c{last}_{last}")


def test_detour_toward_the_end(make_network: MakeNetwork) -> None:
    """H01: the restricted r is a detour of s; a is its shortest hop."""
    pathfinder = Pathfinder(make_network("s-a a-g s-r r-g", types={"r": R}))

    detours = pathfinder.detour_hops("s")

    assert costed(pathfinder, detours) == [("r", 3)]
    assert link_names(detours) == ["s-r"]
    assert hop_names(pathfinder.next_hops("s")) == ["a"]


def test_sideways_neighbor_is_a_detour(make_network: MakeNetwork) -> None:
    """H02: b is as far from g as s, and still a detour of s."""
    pathfinder = Pathfinder(make_network("s-a a-g s-b b-c c-g"))

    assert costed(pathfinder, pathfinder.detour_hops("s")) == [("b", 3)]


def test_backward_and_farther_neighbors_are_detours(
    make_network: MakeNetwork,
) -> None:
    """H03: a detour may lead back to s or farther from g.

    Whether a drone may take it is up to the caller (DetourPolicy).
    """
    back = Pathfinder(make_network("s-a a-g s-r r-g", types={"r": R}))
    assert costed(back, back.detour_hops("a")) == [("s", 3)]
    assert costed(back, back.detour_hops("r")) == [("s", 3)]

    farther = Pathfinder(
        make_network("s-a a-g s-r r-x x-y y-g", types={"r": R})
    )
    assert costed(farther, farther.detour_hops("s")) == [("r", 5)]


def test_shortest_hops_are_not_detours(make_network: MakeNetwork) -> None:
    """H04: next_hops and detour_hops never share a zone.

    Unlike the first detour rule, an all-normal map has detours too
    (backward ones).
    """
    both = Pathfinder(
        make_network("s-u u-g s-r r-g", types={"u": R, "r": R})
    )
    assert hop_names(both.next_hops("s")) == ["u", "r"]
    assert both.detour_hops("s") == []

    normal = Pathfinder(make_network("s-a a-b b-g s-c c-g"))
    assert hop_names(normal.next_hops("s")) == ["c"]
    assert costed(normal, normal.detour_hops("s")) == [("a", 3)]

    grid = square_grid(make_network, 4)
    pathfinder = Pathfinder(grid)
    assert pathfinder.detour_hops("c0_0") == []
    assert hop_names(pathfinder.detour_hops("c1_1")) == ["c1_0", "c0_1"]
    assert sum(len(pathfinder.detour_hops(name)) for name in grid.zones) == 22


def test_blocked_and_dead_end_neighbors_are_not_detours(
    make_network: MakeNetwork,
) -> None:
    """H05: blocked zones and zones that cannot reach g are left out."""
    blocked = Pathfinder(
        make_network("s-a a-g s-r r-g s-x x-g", types={"r": R, "x": X})
    )
    assert costed(blocked, blocked.detour_hops("s")) == [("r", 3)]
    assert blocked.detour_hops("x") == []

    dead_end = Pathfinder(make_network("s-a a-g s-x x-z", types={"x": X}))
    assert dead_end.detour_hops("s") == []


def test_self_loop_is_not_a_detour(make_network: MakeNetwork) -> None:
    """H06: a zone is never its own detour."""
    at_s = Pathfinder(make_network("s-a a-g s-r r-g s-s", types={"r": R}))
    assert costed(at_s, at_s.detour_hops("s")) == [("r", 3)]

    at_a = Pathfinder(make_network("s-a a-g s-r r-g a-a", types={"r": R}))
    assert costed(at_a, at_a.detour_hops("a")) == [("s", 3)]


def test_no_detours_from_end_or_unreachable_zones(
    make_network: MakeNetwork,
) -> None:
    """H07: the end zone and a zone cut off from it have no detours."""
    end = Pathfinder(make_network("s-a a-g s-r r-g", types={"r": R}))
    assert end.detour_hops("g") == []

    cut_off = Pathfinder(make_network("s-a a-g", isolated=("z",)))
    assert cut_off.detour_hops("z") == []


def test_detours_by_total_cost_then_declaration(
    make_network: MakeNetwork,
) -> None:
    """H08: cheapest total cost first; ties keep declaration order.

    The order holds whichever end of a connection the zone is on.
    """
    by_cost = Pathfinder(make_network("s-a a-g s-b b-g a-b"))
    assert costed(by_cost, by_cost.detour_hops("a")) == [
        ("b", 2), ("s", 3)
    ]

    tie = Pathfinder(
        make_network("s-a a-g s-b b-c c-g s-r r-g", types={"r": R})
    )
    assert costed(tie, tie.detour_hops("s")) == [("b", 3), ("r", 3)]

    declared = Pathfinder(
        make_network(
            "s-a a-g s-r2 r2-g s-r1 r1-g", types={"r1": R, "r2": R}
        )
    )
    assert hop_names(declared.detour_hops("s")) == ["r2", "r1"]

    reversed_ends = Pathfinder(
        make_network(
            "r2-s s-a a-g r2-g r1-s r1-g", types={"r1": R, "r2": R}
        )
    )
    detours = reversed_ends.detour_hops("s")
    assert hop_names(detours) == ["r2", "r1"]
    assert link_names(detours) == ["r2-s", "r1-s"]


def test_detour_hops_of_unknown_zone_raises(
    make_network: MakeNetwork,
) -> None:
    """H09: an unknown zone name raises ZoneNotFoundError."""
    pathfinder = Pathfinder(make_network("s-a a-g"))

    with pytest.raises(ZoneNotFoundError) as excinfo:
        pathfinder.detour_hops("nope")
    assert excinfo.value.zone_name == "nope"


def test_detour_away_from_the_end_zone(make_network: MakeNetwork) -> None:
    """H10: a detour two hops from g, not next to it."""
    pathfinder = Pathfinder(
        make_network("s-a a-b b-g s-r r-b", types={"r": R})
    )

    assert pathfinder.distance("s") == 3
    assert hop_names(pathfinder.next_hops("s")) == ["a"]
    assert costed(pathfinder, pathfinder.detour_hops("s")) == [("r", 4)]


@pytest.mark.parametrize(
    "member",
    [None, *(entry[0] for entry in PROVIDED_MAP_DETOURS)],
    ids=["subject", *(map_id(entry[0]) for entry in PROVIDED_MAP_DETOURS)],
)
def test_detours_and_next_hops_split_the_neighbors(
    write_map: WriteMap,
    provided_map: Callable[[str], str],
    member: str | None,
) -> None:
    """H11: on real maps, next_hops and detour_hops split the neighbors.

    For every zone that can reach the end and is not it, the two lists
    together are exactly its other neighbors that can reach the end;
    detours cost more than the zone's distance, come cheapest first and
    never repeat a zone. Other zones have no detours.
    """
    text = SUBJECT_SAMPLE_MAP if member is None else provided_map(member)
    network = MapParser(write_map(text)).parse().network
    pathfinder = Pathfinder(network)

    for name in network.zones:
        here = pathfinder.distance(name)
        detours = pathfinder.detour_hops(name)
        if here is None or here == 0:
            assert detours == [], name
            continue
        neighbors: list[str] = []
        for connection in network.neighbors(name):
            other = connection.other_end(name)
            reachable = pathfinder.distance(other) is not None
            if other != name and reachable and other not in neighbors:
                neighbors.append(other)
        names = hop_names(pathfinder.next_hops(name)) + hop_names(detours)
        assert sorted(names) == sorted(neighbors), name
        totals = [total for _, total in costed(pathfinder, detours)]
        assert all(total > here for total in totals), name
        assert totals == sorted(totals), name
        assert len(set(hop_names(detours))) == len(detours), name


def test_subject_sample_map_detours(write_map: WriteMap) -> None:
    """H12 (a): every zone's detours on the subject's example map.

    The scheduler only uses hub -> roof1 here; the others lead back
    through the drone's own zone and are never allowed.
    """
    network = MapParser(write_map(SUBJECT_SAMPLE_MAP)).parse().network
    pathfinder = Pathfinder(network)

    assert {
        name: costed(pathfinder, pathfinder.detour_hops(name))
        for name in network.zones
    } == {
        "hub": [("roof1", 4)],
        "roof1": [("hub", 4)],
        "roof2": [("roof1", 4)],
        "corridorA": [("hub", 4)],
        "tunnelB": [("corridorA", 3)],
        "goal": [],
        "obstacleX": [],
    }


@pytest.mark.parametrize(
    ("member", "count"),
    PROVIDED_MAP_DETOURS,
    ids=[map_id(entry[0]) for entry in PROVIDED_MAP_DETOURS],
)
def test_provided_map_detour_counts(
    write_map: WriteMap,
    provided_map: Callable[[str], str],
    member: str,
    count: int,
) -> None:
    """H12 (b): how many detour hops each provided map has in all."""
    network = MapParser(write_map(provided_map(member))).parse().network
    pathfinder = Pathfinder(network)

    total = sum(len(pathfinder.detour_hops(name)) for name in network.zones)
    assert total == count
