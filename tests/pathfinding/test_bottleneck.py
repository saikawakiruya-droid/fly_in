"""Tests for droneflow.pathfinding.bottleneck (BN01-BN12, E01-E02).

``A`` is ``ConnectionBottleneck`` (every connection, both ways) and ``B``
is ``ShortestHopBottleneck`` (only the hops ``Pathfinder.next_hops``
offers). Small networks come from the shared ``make_network`` fixture;
BN12 compares A with a brute-force minimum cut on random networks, and
E01/E02 go through the parser with the subject's sample map and the ten
provided maps (read by the shared ``provided_map`` fixture).
"""

import copy
import random
from itertools import combinations
from typing import Callable

import pytest

from droneflow.errors import UnreachableGoalError
from droneflow.models.connection import Connection
from droneflow.models.network import Network
from droneflow.models.world import World
from droneflow.models.zone import Zone, ZoneType
from droneflow.pathfinding.bottleneck import (
    ConnectionBottleneck,
    ShortestHopBottleneck,
)
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.pathfinding.zone_flow import Bottleneck

MakeNetwork = Callable[..., Network]
LoadWorld = Callable[[str], World]
Shown = tuple[int, list[str], list[str], bool]
Finder = ConnectionBottleneck | ShortestHopBottleneck

R = ZoneType.RESTRICTED
X = ZoneType.BLOCKED


def show(bottleneck: Bottleneck) -> Shown:
    """Return the throughput, zone names, connection names and limits_flow."""
    return (
        bottleneck.throughput,
        [zone.name for zone in bottleneck.zones],
        [connection.name for connection in bottleneck.connections],
        bottleneck.limits_flow,
    )


def cut_capacity(bottleneck: Bottleneck) -> int:
    """Return the summed capacity of the zones and connections in the cut."""
    total = sum(c.max_link_capacity for c in bottleneck.connections)
    for zone in bottleneck.zones:
        assert zone.max_drones is not None, f"{zone.name} is unlimited"
        total += zone.max_drones
    return total


def finder_a(network: Network) -> ConnectionBottleneck:
    """Return finder A for the network."""
    return ConnectionBottleneck(network)


def finder_b(network: Network) -> ShortestHopBottleneck:
    """Return finder B for the network (builds its Pathfinder)."""
    return ShortestHopBottleneck(network, Pathfinder(network))


# --- the two finders --------------------------------------------------


def test_a_uses_connections_both_ways(make_network: MakeNetwork) -> None:
    """BN01: a-s and g-a are declared backward; both finders still pass 1."""
    network = make_network("a-s g-a")

    assert show(finder_a(network).find(5)) == (1, [], ["a-s"], True)
    assert show(finder_b(network).find(5)) == (1, [], ["a-s"], True)


def test_b_skips_connections_off_the_shortest_routes(
    make_network: MakeNetwork,
) -> None:
    """BN02: B loses the longer s-b-c-g route that A counts."""
    network = make_network("s-a a-g s-b b-c c-g")

    assert show(finder_a(network).find(5)) == (2, [], ["s-a", "s-b"], True)
    assert show(finder_b(network).find(5)) == (1, [], ["s-a"], True)


def test_restricted_zone_counts_by_capacity_only(
    make_network: MakeNetwork,
) -> None:
    """BN03 a): restricted r still passes max_drones (1) per turn."""
    network = make_network(
        "s-r r-g", types={"r": R}, links={"s-r": 3, "r-g": 3}
    )

    assert show(finder_a(network).find(5)) == (1, ["r"], [], True)


def test_restricted_route_is_not_shortest_for_b(
    make_network: MakeNetwork,
) -> None:
    """BN03 b): A counts the way through r; B drops it (turn cost 2)."""
    network = make_network("s-r r-g s-a a-g", types={"r": R})

    assert show(finder_a(network).find(5)) == (2, [], ["s-r", "s-a"], True)
    assert show(finder_b(network).find(5)) == (1, [], ["s-a"], True)


@pytest.mark.parametrize("make_finder", [finder_a, finder_b], ids=["A", "B"])
def test_blocked_zone_is_not_counted(
    make_network: MakeNetwork, make_finder: Callable[[Network], Finder]
) -> None:
    """BN04: the wide way through blocked x adds nothing."""
    network = make_network(
        "s-x x-g s-a a-g",
        types={"x": X},
        capacity={"x": 5},
        links={"s-x": 5, "x-g": 5},
    )

    assert show(make_finder(network).find(5)) == (1, [], ["s-a"], True)


@pytest.mark.parametrize("make_finder", [finder_a, finder_b], ids=["A", "B"])
def test_self_loops_are_not_counted(
    make_network: MakeNetwork, make_finder: Callable[[Network], Finder]
) -> None:
    """BN05: wide self-loops a-a and s-s add nothing."""
    network = make_network("s-a a-a a-g s-s", links={"a-a": 9, "s-s": 9})

    assert show(make_finder(network).find(5)) == (1, [], ["s-a"], True)


@pytest.mark.parametrize("limit", [0, -1])
@pytest.mark.parametrize("make_finder", [finder_a, finder_b], ids=["A", "B"])
def test_limit_below_one_is_rejected(
    make_network: MakeNetwork,
    make_finder: Callable[[Network], Finder],
    limit: int,
) -> None:
    """BN06: find raises ValueError (B builds its Pathfinder first)."""
    finder = make_finder(make_network("s-g"))

    with pytest.raises(ValueError):
        finder.find(limit)


def test_finder_can_be_used_again(
    load_world: LoadWorld, subject_map: str
) -> None:
    """BN07: each find starts afresh; room, exact and over the limit."""
    network = load_world(subject_map).network
    a = finder_a(network)

    first = a.find(1)
    assert show(first) == (1, [], [], False)
    full = a.find(5)
    assert show(full) == (2, [], ["hub-roof1", "hub-corridorA"], True)
    assert a.find(2) == full
    assert a.find(1) == first
    assert show(finder_b(network).find(1)) == (
        1, [], ["hub-corridorA"], True
    )


@pytest.mark.parametrize("make_finder", [finder_a, finder_b], ids=["A", "B"])
def test_all_routes_shortest_gives_the_same_result(
    make_network: MakeNetwork, make_finder: Callable[[Network], Finder]
) -> None:
    """BN08: with no detour (S11), A and B agree."""
    network = make_network("s-a s-b a-g b-g")

    assert show(make_finder(network).find(4)) == (
        2, [], ["s-a", "s-b"], True
    )


def test_narrow_connection_far_from_the_start(
    make_network: MakeNetwork,
) -> None:
    """BN09: a-g (1) is the only minimum cut (S12), so it is returned."""
    network = make_network("s-a a-g", capacity={"a": 2}, links={"s-a": 2})

    assert show(finder_a(network).find(2)) == (1, [], ["a-g"], True)


def test_unreachable_end(make_network: MakeNetwork) -> None:
    """BN10: A returns no flow; B fails earlier, in Pathfinder."""
    network = make_network("s-a b-g")

    bottleneck = finder_a(network).find(5)

    assert bottleneck == Bottleneck(0, (), ())
    assert bottleneck.limits_flow is False
    with pytest.raises(UnreachableGoalError):
        Pathfinder(network)


def test_network_is_not_changed(make_network: MakeNetwork) -> None:
    """BN11: neither finder writes to the network."""
    network = make_network("s-a a-g s-b b-g")
    zones = copy.deepcopy(network.zones)
    connections = copy.deepcopy(network.connections)

    finder_a(network).find(3)
    finder_b(network).find(3)

    assert network.zones == zones
    assert network.connections == connections


# --- property: the max-flow min-cut theorem (BN12) --------------------

RANDOM_SEEDS = range(40)

Element = tuple[int, Zone | Connection]


def end_reachable(network: Network, removed: list[Element]) -> bool:
    """Return whether the end is reachable once ``removed`` is cut out.

    A depth-first search over the connections left, through zones that
    are traversable and not removed.
    """
    gone = {id(item) for _, item in removed}
    start = network.start_zone.name
    end = network.end_zone.name
    seen = {start}
    stack = [start]
    while stack:
        here = stack.pop()
        if here == end:
            return True
        for connection in network.neighbors(here):
            if id(connection) in gone:
                continue
            there = connection.other_end(here)
            zone = network.get_zone(there)
            if there in seen or id(zone) in gone:
                continue
            if not zone.zone_type.is_traversable:
                continue
            seen.add(there)
            stack.append(there)
    return False


def brute_force_min_cut(network: Network) -> int:
    """Return the smallest capacity whose removal cuts start from end.

    The elements that can be cut are the traversable hubs (start and end
    are unlimited) and the connections that are not self-loops. Every
    element weighs at least 1, so subsets of size k are only tried while
    k is below the best cut found. Returns 0 if the end is unreachable.
    """
    elements: list[Element] = []
    for zone in network.zones.values():
        if zone.max_drones is None or not zone.zone_type.is_traversable:
            continue
        if zone.name in (network.start_zone.name, network.end_zone.name):
            continue
        elements.append((zone.max_drones, zone))
    for connection in network.connections:
        if connection.zone_a != connection.zone_b:
            elements.append((connection.max_link_capacity, connection))
    if not end_reachable(network, []):
        return 0
    best = sum(weight for weight, _ in elements)
    size = 1
    while size < best and size <= len(elements):
        for subset in combinations(elements, size):
            weight = sum(w for w, _ in subset)
            if weight < best and not end_reachable(network, list(subset)):
                best = weight
        size += 1
    return best


def random_network(rng: random.Random, make_network: MakeNetwork) -> Network:
    """Draw 2-5 hubs and hub count + 1..5 distinct connections.

    Hubs are BLOCKED 15% of the time, RESTRICTED 20%, with max_drones 1-3;
    connections have a capacity of 1-3. Every hub is registered even
    without a connection.
    """
    n = rng.randint(2, 5)
    hubs = [f"h{i}" for i in range(n)]
    nodes = ["s", "g", *hubs]
    wanted = min(n + rng.randint(1, 5), len(nodes) * (len(nodes) - 1) // 2)
    pairs: list[tuple[str, str]] = []
    while len(pairs) < wanted:
        zone_a, zone_b = rng.sample(nodes, 2)
        if (zone_a, zone_b) not in pairs and (zone_b, zone_a) not in pairs:
            pairs.append((zone_a, zone_b))
    types: dict[str, ZoneType] = {}
    capacity: dict[str, int] = {}
    for hub in hubs:
        roll = rng.random()
        if roll < 0.15:
            types[hub] = X
        elif roll < 0.35:
            types[hub] = R
        capacity[hub] = rng.randint(1, 3)
    links = {f"{a}-{b}": rng.randint(1, 3) for a, b in pairs}
    return make_network(
        " ".join(f"{a}-{b}" for a, b in pairs),
        types=types,
        isolated=tuple(hubs),
        capacity=capacity,
        links=links,
    )


def describe(network: Network) -> str:
    """Return a one-line description of a network for failure messages."""
    zones = [
        f"{z.name}:{z.zone_type.value}:{z.max_drones}"
        for z in network.zones.values()
    ]
    links = [f"{c.name}:{c.max_link_capacity}" for c in network.connections]
    return f"zones={zones} links={links}"


def test_matches_brute_force_min_cut(make_network: MakeNetwork) -> None:
    """BN12: A's throughput and cut agree with a brute-force minimum cut.

    For each random network: A's throughput is min(cut, limit), a cut is
    reported exactly when the limit reaches it, and the reported cut has
    the throughput as capacity. B never passes more than A, and its cut
    (if any) matches its throughput; B can only fail to build when the
    end is unreachable.
    """
    for seed in RANDOM_SEEDS:
        network = random_network(random.Random(seed), make_network)
        where = f"seed {seed}: {describe(network)}"
        mc = brute_force_min_cut(network)
        a = finder_a(network)
        for limit in (1, max(1, mc), mc + 1, 100):
            result = a.find(limit)
            assert result.throughput == min(mc, limit), where
            assert result.limits_flow == (mc > 0 and limit >= mc), where
            if result.limits_flow:
                assert cut_capacity(result) == result.throughput, where
        try:
            pathfinder = Pathfinder(network)
        except UnreachableGoalError:
            assert mc == 0, where
            continue
        b = ShortestHopBottleneck(network, pathfinder).find(100)
        assert b.throughput <= a.find(100).throughput, where
        if b.limits_flow:
            assert cut_capacity(b) == b.throughput, where


# --- through the parser -----------------------------------------------


@pytest.mark.parametrize("limit", [5, 3])
def test_subject_sample_map(
    load_world: LoadWorld, subject_map: str, limit: int
) -> None:
    """E01: A passes 2 (roof1 and corridorA ways), B only 1."""
    network = load_world(subject_map).network

    assert show(finder_a(network).find(limit)) == (
        2, [], ["hub-roof1", "hub-corridorA"], True
    )
    assert show(finder_b(network).find(limit)) == (
        1, [], ["hub-corridorA"], True
    )


Expected = tuple[int, list[str], list[str]]

# (member, nb_drones, A, B) -- B is None when it is the same as A.
PROVIDED_MAPS: list[tuple[str, int, Expected, Expected | None]] = [
    ("maps/easy/01_linear_path.txt", 2, (1, [], ["start-waypoint1"]), None),
    ("maps/easy/02_simple_fork.txt", 4, (2, [], ["start-junction"]), None),
    ("maps/easy/03_basic_capacity.txt", 4, (2, ["bottleneck"], []), None),
    (
        "maps/medium/01_dead_end_trap.txt", 5,
        (1, [], ["junction-correct_path"]), None,
    ),
    (
        "maps/medium/02_circular_loop.txt", 6,
        (1, [], ["loop_b-exit_point"]), None,
    ),
    (
        "maps/medium/03_priority_puzzle.txt", 5,
        (2, [], ["start-slow_path1", "start-fast_junction"]),
        (1, [], ["start-fast_junction"]),
    ),
    (
        "maps/hard/01_maze_nightmare.txt", 8,
        (1, [], ["maze_c2-bottleneck"]), (1, [], ["maze_a1-maze_a2"]),
    ),
    (
        "maps/hard/02_capacity_hell.txt", 12,
        (1, [], ["final_bottleneck-goal"]), (1, [], ["start-gate3"]),
    ),
    (
        "maps/hard/03_ultimate_challenge.txt", 15,
        (1, ["final_gate3"], []), (1, [], ["start-dist_gate1"]),
    ),
    (
        "maps/challenger/01_the_impossible_dream.txt", 25,
        (1, [], ["start-gate_hell1"]), None,
    ),
]


def map_id(member: str) -> str:
    """Return a short test id such as ``easy/01_linear_path``."""
    return member.removeprefix("maps/").removesuffix(".txt")


@pytest.mark.parametrize(
    ("member", "nb_drones", "expected_a", "expected_b"),
    PROVIDED_MAPS,
    ids=[map_id(entry[0]) for entry in PROVIDED_MAPS],
)
def test_provided_maps(
    load_world: LoadWorld,
    provided_map: Callable[[str], str],
    member: str,
    nb_drones: int,
    expected_a: Expected,
    expected_b: Expected | None,
) -> None:
    """E02: the measured bottlenecks of the workflow table (d)."""
    world = load_world(provided_map(member))
    assert world.nb_drones == nb_drones

    a = finder_a(world.network).find(world.nb_drones)
    b = finder_b(world.network).find(world.nb_drones)

    assert show(a) == (*expected_a, True)
    assert show(b) == (*(expected_b or expected_a), True)
