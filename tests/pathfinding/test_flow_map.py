"""Tests for pathfinder (Route, last_turn, FlowGraph, FlowMap, Pathfinder).

``FlowMap`` holds a ``Network``, which has no ``__eq__``, so flow maps
are compared by their routes, their last turn and the contents of the
held map (``zone_caps`` and ``link_caps``), never with ``==``.
"""

import dataclasses
import time
from pathlib import Path
from typing import Callable

import pytest

from errors import ParseError, UnreachableGoalError
from map_parser import MapParser
from pathfinder import FlowGraph, Pathfinder, Route, last_turn
from world import Network, World, ZoneType

MakeNetwork = Callable[..., Network]
WriteMap = Callable[[str], Path]
LoadWorld = Callable[[str], World]

R = ZoneType.RESTRICTED
P = ZoneType.PRIORITY
B = ZoneType.BLOCKED


def route(text: str, rate: int, turns: int) -> Route:
    """Return the route through the space separated zones of ``text``."""
    return Route(tuple(text.split()), rate, turns)


def zone_caps(network: Network) -> dict[str, int | None]:
    """Return ``max_drones`` of every zone, in declaration order."""
    return {name: zone.max_drones for name, zone in network.zones.items()}


def link_caps(network: Network) -> list[tuple[str, int]]:
    """Return the name and capacity of every connection, in order."""
    return [(c.name, c.max_link_capacity) for c in network.connections]


# --- last_turn and Route.arrival_turn ---------------------------------


def test_last_turn_with_no_drones_is_zero() -> None:
    """LT01: no drones need no route and no turn."""
    assert last_turn((), 0) == 0
    assert last_turn((route("s g", 1, 1),), -3) == 0


def test_last_turn_without_routes_raises() -> None:
    """LT02: drones without a route are the caller's mistake."""
    with pytest.raises(ValueError, match="no route to send the drones along"):
        last_turn((), 1)


@pytest.mark.parametrize(("nb_drones", "expected"), [(1, 3), (2, 4), (4, 6)])
def test_last_turn_one_route_of_rate_one(
    nb_drones: int, expected: int
) -> None:
    """LT03: one drone per turn arrives from turn ``turns`` on."""
    assert last_turn((route("s a b g", 1, 3),), nb_drones) == expected


@pytest.mark.parametrize(
    ("nb_drones", "expected"), [(1, 2), (2, 2), (3, 3), (4, 3), (5, 4)]
)
def test_last_turn_one_route_of_rate_two(
    nb_drones: int, expected: int
) -> None:
    """LT04: ``rate`` drones arrive each turn; a remainder takes a turn."""
    assert last_turn((route("s a g", 2, 2),), nb_drones) == expected


@pytest.mark.parametrize(
    ("nb_drones", "expected"), [(1, 2), (2, 3), (3, 3), (4, 4), (5, 4)]
)
def test_last_turn_two_routes_of_different_lengths(
    nb_drones: int, expected: int
) -> None:
    """LT05: the routes' deliveries add up (by turn 3: 2 + 1 drones)."""
    routes = (route("s a g", 1, 2), route("s r g", 1, 3))
    assert last_turn(routes, nb_drones) == expected


@pytest.mark.parametrize(
    ("nb_drones", "expected"), [(1, 2), (3, 4), (8, 9), (9, 10), (10, 10)]
)
def test_last_turn_ignores_routes_longer_than_the_turn(
    nb_drones: int, expected: int
) -> None:
    """LT06: a route delivers nothing before its ``turns``; at turn 10 the
    long route brings one drone too, so ten drones still take 10."""
    routes = (route("s a g", 1, 2), route("x", 1, 10))
    assert last_turn(routes, nb_drones) == expected


def test_route_arrival_turn() -> None:
    """LT07: a drone enters the first zone on the turn it leaves."""
    assert route("s a g", 1, 2).arrival_turn(1) == 2
    assert route("s a g", 1, 2).arrival_turn(3) == 4


# --- the flow and its routes ------------------------------------------


def test_single_path(make_network: MakeNetwork) -> None:
    """FM01: one path, one drone per turn."""
    flow_map = Pathfinder(make_network("s-a a-g")).flow_map(3)

    assert flow_map.routes == (route("s a g", 1, 2),)
    assert flow_map.last_turn == 4


def test_fork_with_one_drone(make_network: MakeNetwork) -> None:
    """FM02: one drone needs one route, the first declared of equal ones."""
    flow_map = Pathfinder(make_network("s-a a-g s-b b-g")).flow_map(1)

    assert flow_map.routes == (route("s a g", 1, 2),)
    assert flow_map.last_turn == 2


@pytest.mark.parametrize(("nb_drones", "expected"), [(2, 2), (5, 4)])
def test_fork_with_more_drones(
    make_network: MakeNetwork, nb_drones: int, expected: int
) -> None:
    """FM03: from two drones on, both branches are used."""
    flow_map = Pathfinder(make_network("s-a a-g s-b b-g")).flow_map(nb_drones)

    assert flow_map.routes == (route("s a g", 1, 2), route("s b g", 1, 2))
    assert flow_map.last_turn == expected


def test_narrow_merge(make_network: MakeNetwork) -> None:
    """FM04: a merge zone of capacity 1 lets one drone per turn through,
    so the second branch is not used."""
    flow_map = Pathfinder(make_network("s-a s-b a-m b-m m-g")).flow_map(3)

    assert flow_map.routes == (route("s a m g", 1, 3),)
    assert flow_map.last_turn == 5


def test_wide_merge(make_network: MakeNetwork) -> None:
    """FM05: two routes share a merge zone wide enough for both."""
    network = make_network(
        "s-a s-b a-m b-m m-g", capacity={"m": 2}, links={"m-g": 2}
    )
    flow_map = Pathfinder(network).flow_map(4)

    assert flow_map.routes == (
        route("s a m g", 1, 3), route("s b m g", 1, 3)
    )
    assert flow_map.last_turn == 4


def test_rate_limited_by_a_connection(make_network: MakeNetwork) -> None:
    """FM06: the connection of capacity 2 sets the rate, not the zone."""
    network = make_network(
        "s-a a-g", capacity={"a": 3}, links={"s-a": 2, "a-g": 3}
    )
    flow_map = Pathfinder(network).flow_map(4)

    assert flow_map.routes == (route("s a g", 2, 2),)
    assert flow_map.last_turn == 3


def test_rate_limited_by_a_zone(make_network: MakeNetwork) -> None:
    """FM07: the zone's in-out arc of capacity 1 sets the rate."""
    network = make_network(
        "s-a a-g", capacity={"a": 1}, links={"s-a": 3, "a-g": 3}
    )
    flow_map = Pathfinder(network).flow_map(4)

    assert flow_map.routes == (route("s a g", 1, 2),)
    assert flow_map.last_turn == 5


def test_restricted_zone_takes_two_turns(make_network: MakeNetwork) -> None:
    """FM08: the entry cost 2 of a restricted zone is in ``turns``."""
    network = make_network("s-r r-g", types={"r": R})
    flow_map = Pathfinder(network).flow_map(2)

    assert flow_map.routes == (route("s r g", 1, 3),)
    assert flow_map.last_turn == 4


@pytest.mark.parametrize(
    ("nb_drones", "routes", "expected"),
    [
        (1, (route("s a g", 1, 2),), 2),
        (2, (route("s a g", 1, 2),), 3),
        (3, (route("s a g", 1, 2), route("s r g", 1, 3)), 3),
    ],
)
def test_restricted_detour_used_only_when_it_helps(
    make_network: MakeNetwork,
    nb_drones: int,
    routes: tuple[Route, ...],
    expected: int,
) -> None:
    """FM09: with two drones the path through r (3 turns) cannot lower
    T = 3, so the search stops; with three it does."""
    network = make_network("s-a a-g s-r r-g", types={"r": R})
    flow_map = Pathfinder(network).flow_map(nb_drones)

    assert flow_map.routes == routes
    assert flow_map.last_turn == expected


@pytest.mark.parametrize(
    ("nb_drones", "routes"),
    [
        (4, (route("s a g", 2, 2),)),
        (5, (route("s a g", 2, 2), route("s b g", 1, 2))),
    ],
)
def test_route_kept_only_when_it_lowers_the_last_turn(
    make_network: MakeNetwork, nb_drones: int, routes: tuple[Route, ...]
) -> None:
    """FM10: with four drones adding b keeps T = 3, so the flow without it
    is kept (only a strictly lower T replaces the best)."""
    network = make_network(
        "s-a a-g s-b b-g", capacity={"a": 2}, links={"s-a": 2, "a-g": 2}
    )
    flow_map = Pathfinder(network).flow_map(nb_drones)

    assert flow_map.routes == routes
    assert flow_map.last_turn == 3


@pytest.mark.parametrize(
    ("nb_drones", "routes"),
    [
        (1, (route("s p g", 1, 2),)),
        (2, (route("s p g", 1, 2), route("s a g", 1, 2))),
    ],
)
def test_priority_breaks_ties(
    make_network: MakeNetwork, nb_drones: int, routes: tuple[Route, ...]
) -> None:
    """FM11: among equally long routes the one through priority p wins,
    even though a is declared first, and comes first in ``routes``."""
    network = make_network("s-a a-g s-p p-g", types={"p": P})
    flow_map = Pathfinder(network).flow_map(nb_drones)

    assert flow_map.routes == routes
    assert flow_map.last_turn == 2


def test_longer_priority_route_is_not_taken(
    make_network: MakeNetwork,
) -> None:
    """FM12: priority only breaks ties between routes of equal length."""
    network = make_network("s-p p-q q-g s-a a-g", types={"p": P})
    flow_map = Pathfinder(network).flow_map(1)

    assert flow_map.routes == (route("s a g", 1, 2),)
    assert flow_map.last_turn == 2


def test_most_priority_zones_win(make_network: MakeNetwork) -> None:
    """FM13: of three routes of equal length (0, 1 and 2 priority zones),
    the one through the most priority zones is taken."""
    network = make_network(
        "s-a a-b b-g s-p p-q q-g s-x x-y y-g",
        types={"p": P, "x": P, "y": P},
    )
    flow_map = Pathfinder(network).flow_map(1)

    assert flow_map.routes == (route("s x y g", 1, 3),)


@pytest.mark.parametrize(
    ("nb_drones", "routes"),
    [
        (1, (route("s a b g", 1, 3),)),
        (2, (route("s a d g", 1, 3), route("s c b g", 1, 3))),
    ],
)
def test_back_arc_rearranges_the_routes(
    make_network: MakeNetwork, nb_drones: int, routes: tuple[Route, ...]
) -> None:
    """FM14: the second shortest path goes back along a-b and cancels it;
    the routes are split from the flow left after that (a-b unused)."""
    network = make_network("s-a a-b b-g s-c c-b a-d d-g")
    flow_map = Pathfinder(network).flow_map(nb_drones)

    assert flow_map.routes == routes
    assert flow_map.last_turn == 3


def test_flow_graph_without_a_path(make_network: MakeNetwork) -> None:
    """FM14 (FlowGraph): a blocked zone gives no path and no route."""
    graph = FlowGraph(make_network("s-x x-g", types={"x": B}), 3)

    assert graph.shortest_path() is None
    assert graph.routes() == ()


def test_flow_graph_push_and_routes(make_network: MakeNetwork) -> None:
    """FM14 (FlowGraph): the arcs and costs of one path, then its route.

    The weight is (3 + 1) x (3 + 1) = 16: three drones, three zones.
    """
    graph = FlowGraph(make_network("s-a a-g"), 3)
    assert graph.routes() == ()

    path = graph.shortest_path()
    assert path is not None
    assert [arc.cost for arc in path] == [16, 0, 16]
    assert [arc.turns for arc in path] == [1, 0, 1]

    graph.push(path, 1)
    assert graph.routes() == (route("s a g", 1, 2),)
    assert graph.shortest_path() is None


def test_flow_graph_priority_cost(make_network: MakeNetwork) -> None:
    """FM14 (FlowGraph): the arc into a priority zone costs 1 less."""
    graph = FlowGraph(make_network("s-a a-g s-p p-g", types={"p": P}), 2)

    path = graph.shortest_path()
    assert path is not None
    assert [arc.cost for arc in path] == [14, 0, 15]


def test_start_and_end_are_unlimited(make_network: MakeNetwork) -> None:
    """FM15: the start and end zones take any number of drones, and
    entering a restricted end costs two turns."""
    wide = Pathfinder(make_network("s-g", links={"s-g": 3})).flow_map(5)
    assert wide.routes == (route("s g", 3, 1),)
    assert wide.last_turn == 2

    slow = Pathfinder(make_network("s-g", types={"g": R})).flow_map(2)
    assert slow.routes == (route("s g", 1, 2),)
    assert slow.last_turn == 3


@pytest.mark.parametrize(
    ("nb_drones", "rate", "expected"), [(4, 4, 2), (7, 5, 3)]
)
def test_hub_without_max_drones_is_unlimited(
    make_network: MakeNetwork, nb_drones: int, rate: int, expected: int
) -> None:
    """FM16: a hub with no ``max_drones`` is unlimited (the drone count),
    so the connections of capacity 5 set the rate."""
    base = make_network("s-a a-g", links={"s-a": 5, "a-g": 5})
    network = Network()
    for name, zone in base.zones.items():
        network.add_zone(
            dataclasses.replace(zone, max_drones=None) if name == "a"
            else zone
        )
    for connection in base.connections:
        network.add_connection(connection)
    flow_map = Pathfinder(network).flow_map(nb_drones)

    assert flow_map.routes == (route("s a g", rate, 2),)
    assert flow_map.last_turn == expected


# --- the held map -----------------------------------------------------


def test_held_map_keeps_only_what_the_routes_use(
    make_network: MakeNetwork,
) -> None:
    """HM01: b, c and their connections are left out."""
    held = Pathfinder(make_network("s-a a-g s-b b-c c-g")).flow_map(1).network

    assert zone_caps(held) == {"s": None, "g": None, "a": 1}
    assert link_caps(held) == [("s-a", 1), ("a-g", 1)]


def test_held_map_has_no_blocked_zone(make_network: MakeNetwork) -> None:
    """HM02: a blocked zone has no node, so it is never held."""
    network = make_network("s-x x-g s-a a-b b-g", types={"x": B})
    flow_map = Pathfinder(network).flow_map(2)

    assert flow_map.routes == (route("s a b g", 1, 3),)
    assert flow_map.last_turn == 4
    assert zone_caps(flow_map.network) == {
        "s": None, "g": None, "a": 1, "b": 1
    }
    assert link_caps(flow_map.network) == [
        ("s-a", 1), ("a-b", 1), ("b-g", 1)
    ]


def test_held_capacities_are_drones_per_turn(
    load_world: LoadWorld, subject_map: str
) -> None:
    """HM03: the held capacities are what flows per turn, not the parsed
    ones (corridorA and corridorA-tunnelB go from 2 down to 1)."""
    flow_map = Pathfinder(load_world(subject_map).network).flow_map(5)

    assert flow_map.routes == (
        route("hub corridorA tunnelB goal", 1, 3),
        route("hub roof1 roof2 goal", 1, 4),
    )
    assert flow_map.last_turn == 5
    assert zone_caps(flow_map.network) == {
        "hub": None,
        "goal": None,
        "roof1": 1,
        "roof2": 1,
        "corridorA": 1,
        "tunnelB": 1,
    }
    assert link_caps(flow_map.network) == [
        ("hub-roof1", 1),
        ("hub-corridorA", 1),
        ("roof1-roof2", 1),
        ("roof2-goal", 1),
        ("corridorA-tunnelB", 1),
        ("tunnelB-goal", 1),
    ]


def test_shared_zone_and_connection_add_up(
    make_network: MakeNetwork,
) -> None:
    """HM04: m and m-g carry the rates of both routes."""
    network = make_network(
        "s-a s-b a-m b-m m-g", capacity={"m": 2}, links={"m-g": 2}
    )
    held = Pathfinder(network).flow_map(4).network

    assert zone_caps(held) == {
        "s": None, "g": None, "a": 1, "b": 1, "m": 2
    }
    assert link_caps(held) == [
        ("s-a", 1), ("s-b", 1), ("a-m", 1), ("b-m", 1), ("m-g", 2)
    ]


def test_held_map_keeps_order_and_connection_names(
    make_network: MakeNetwork,
) -> None:
    """HM05: connections keep their declared ``zone_a-zone_b`` names (the
    output uses them), even when the route goes the other way."""
    flow_map = Pathfinder(make_network("a-s g-a")).flow_map(2)

    assert flow_map.routes == (route("s a g", 1, 2),)
    assert link_caps(flow_map.network) == [("a-s", 1), ("g-a", 1)]
    assert list(flow_map.network.zones) == ["s", "g", "a"]


def test_held_zones_keep_their_other_attributes(
    load_world: LoadWorld, subject_map: str
) -> None:
    """HM06: only ``max_drones`` changes; position, colour, type and role
    are kept for the views and the resolver."""
    network = load_world(subject_map).network
    held = Pathfinder(network).flow_map(5).network

    for name, zone in held.zones.items():
        original = network.get_zone(name)
        assert (
            dataclasses.replace(zone, max_drones=original.max_drones)
            == original
        )
    assert held.start_zone == network.start_zone
    assert held.end_zone == network.end_zone
    assert held.start_zone.max_drones is None
    assert held.end_zone.max_drones is None


def test_parsed_map_is_left_unchanged(make_network: MakeNetwork) -> None:
    """HM07: the held map is built from new zones and connections."""
    network = make_network(
        "s-a a-g", capacity={"a": 3}, links={"s-a": 2}
    )
    zones = dict(network.zones)
    connections = tuple(network.connections)

    flow_map = Pathfinder(network).flow_map(3)

    assert dict(network.zones) == zones
    assert tuple(network.connections) == connections
    assert network.get_zone("a").max_drones == 3
    assert network.connections[0].max_link_capacity == 2
    assert flow_map.network is not network
    assert flow_map.network.get_zone("a").max_drones == 1


def test_flow_map_for_no_drones(make_network: MakeNetwork) -> None:
    """HM08: without drones the held map has only the start and end."""
    flow_map = Pathfinder(make_network("s-a a-g")).flow_map(0)

    assert flow_map.routes == ()
    assert flow_map.last_turn == 0
    assert zone_caps(flow_map.network) == {"s": None, "g": None}
    assert link_caps(flow_map.network) == []


# --- Pathfinder: construction and end to end --------------------------


@pytest.mark.parametrize(
    ("edges", "types"),
    [
        pytest.param("s-a b-g", {}, id="disconnected"),
        pytest.param("s-x x-g", {"x": B}, id="only-route-blocked"),
        pytest.param("", {}, id="no-connections"),
        pytest.param("s-a a-g", {"g": B}, id="blocked-end"),
    ],
)
def test_unreachable_goal_is_detected_at_construction(
    make_network: MakeNetwork, edges: str, types: dict[str, ZoneType]
) -> None:
    """PF01: a map whose goal cannot be reached fails right away."""
    network = make_network(edges, types=types)
    with pytest.raises(UnreachableGoalError) as excinfo:
        Pathfinder(network)
    assert excinfo.value.zone_name == "s"
    assert excinfo.value.goal_name == "g"
    assert str(excinfo.value) == "goal 'g' is unreachable from 's'"
    assert "line" not in str(excinfo.value)


def test_isolated_zone_does_not_prevent_construction(
    make_network: MakeNetwork,
) -> None:
    """PF02: only the start has to reach the goal; z is not held."""
    flow_map = Pathfinder(
        make_network("s-a a-g", isolated=("z",))
    ).flow_map(1)

    assert flow_map.routes == (route("s a g", 1, 2),)
    assert "z" not in flow_map.network.zones


def test_through_the_parser(write_map: WriteMap, subject_map: str) -> None:
    """PF03: the parsed example gives the routes of HM03; an unreachable
    map parses, and the pathfinder rejects it."""
    world = MapParser(write_map(subject_map)).parse()
    flow_map = Pathfinder(world.network).flow_map(world.nb_drones)
    assert flow_map.routes == (
        route("hub corridorA tunnelB goal", 1, 3),
        route("hub roof1 roof2 goal", 1, 4),
    )
    assert flow_map.last_turn == 5

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


SINGLE_DRONE_TURNS = [
    ("maps/easy/01_linear_path.txt", 3),
    ("maps/easy/02_simple_fork.txt", 3),
    ("maps/easy/03_basic_capacity.txt", 3),
    ("maps/medium/01_dead_end_trap.txt", 4),
    ("maps/medium/02_circular_loop.txt", 5),
    ("maps/medium/03_priority_puzzle.txt", 4),
    ("maps/hard/01_maze_nightmare.txt", 6),
    ("maps/hard/02_capacity_hell.txt", 5),
    ("maps/hard/03_ultimate_challenge.txt", 12),
    ("maps/challenger/01_the_impossible_dream.txt", 19),
]


@pytest.mark.parametrize(
    ("member", "expected"),
    SINGLE_DRONE_TURNS,
    ids=[
        member.removeprefix("maps/").removesuffix(".txt")
        for member, _ in SINGLE_DRONE_TURNS
    ],
)
def test_single_drone_on_provided_maps(
    load_world: LoadWorld,
    provided_map: Callable[[str], str],
    member: str,
    expected: int,
) -> None:
    """PF04: the fastest route of one drone on each provided map."""
    flow_map = Pathfinder(load_world(provided_map(member)).network).flow_map(1)

    assert flow_map.last_turn == expected
    assert flow_map.routes[0].turns == expected


def test_single_drone_on_subject_map(
    load_world: LoadWorld, subject_map: str
) -> None:
    """PF04: one drone on the subject's example takes three turns."""
    flow_map = Pathfinder(load_world(subject_map).network).flow_map(1)

    assert flow_map.last_turn == 3
    assert flow_map.routes[0].turns == 3


@pytest.mark.parametrize(
    ("nb_drones", "nb_routes", "expected"),
    [(1, 1, 38), (2, 2, 38), (25, 2, 50), (100, 2, 87)],
)
def test_grid(
    grid_network: Network, nb_drones: int, nb_routes: int, expected: int
) -> None:
    """PF05: a 20 x 20 grid is solved quickly; the start corner has two
    exits, so two routes at most."""
    began = time.perf_counter()
    flow_map = Pathfinder(grid_network).flow_map(nb_drones)
    elapsed = time.perf_counter() - began

    assert len(flow_map.routes) == nb_routes
    assert all(r.rate == 1 and r.turns == 38 for r in flow_map.routes)
    assert flow_map.last_turn == expected
    assert elapsed < 1.0
