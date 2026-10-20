"""Tests for droneflow.pathfinding.zone_flow (ZF01-ZF19).

Networks come from the shared ``make_network`` fixture; the few shapes it
cannot build (start and end with a ``max_drones``, a hub without one) are
put together from ``Zone`` and ``Connection`` directly. Results are
compared through ``show`` (names rather than objects, so a failure shows
a readable diff).
"""

import dataclasses
from typing import Callable

import pytest

from droneflow.errors import ZoneNotFoundError
from droneflow.models.connection import Connection
from droneflow.models.network import Network
from droneflow.models.zone import Zone, ZoneRole, ZoneType
from droneflow.pathfinding.zone_flow import Bottleneck, ZoneFlowGraph

MakeNetwork = Callable[..., Network]
Shown = tuple[int, list[str], list[str], bool]

X = ZoneType.BLOCKED


def show(bottleneck: Bottleneck) -> Shown:
    """Return the throughput, zone names, connection names and limits_flow."""
    return (
        bottleneck.throughput,
        [zone.name for zone in bottleneck.zones],
        [connection.name for connection in bottleneck.connections],
        bottleneck.limits_flow,
    )


def solve_both_ways(network: Network, limit: int) -> Bottleneck:
    """Add every connection as a hop in both directions, then solve.

    This is what ``ConnectionBottleneck`` does; doing it here keeps these
    tests on ``ZoneFlowGraph`` alone.
    """
    graph = ZoneFlowGraph(network, limit)
    for connection in network.connections:
        graph.add_hop(connection, connection.zone_a, connection.zone_b)
        graph.add_hop(connection, connection.zone_b, connection.zone_a)
    return graph.solve()


def hand_built(
    end_drones: int | None, hub_drones: int | None, link: int
) -> Network:
    """Return s-a-g built from Zone and Connection directly.

    ``end_drones`` is the ``max_drones`` of both start and end (the
    parser would drop it), ``hub_drones`` that of hub a, and ``link`` the
    capacity of both connections.
    """
    network = Network()
    for name, role, max_drones in (
        ("s", ZoneRole.START, end_drones),
        ("g", ZoneRole.END, end_drones),
        ("a", ZoneRole.HUB, hub_drones),
    ):
        network.add_zone(
            Zone(name, 0, 0, ZoneType.NORMAL, role, max_drones=max_drones)
        )
    network.add_connection(Connection("s", "a", link))
    network.add_connection(Connection("a", "g", link))
    return network


# --- Bottleneck -------------------------------------------------------


def test_bottleneck_is_frozen() -> None:
    """ZF01: attributes cannot be assigned; equal values compare equal."""
    bottleneck = Bottleneck(1, (), ())

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(bottleneck, "throughput", 2)

    assert bottleneck == Bottleneck(1, (), ())


@pytest.mark.parametrize(
    ("with_zone", "with_connection", "expected"),
    [
        pytest.param(True, False, True, id="zones-only"),
        pytest.param(False, True, True, id="connections-only"),
        pytest.param(True, True, True, id="both"),
        pytest.param(False, False, False, id="neither"),
    ],
)
def test_limits_flow_means_a_cut_was_found(
    make_network: MakeNetwork,
    with_zone: bool,
    with_connection: bool,
    expected: bool,
) -> None:
    """ZF02: True when zones or connections is not empty."""
    network = make_network("s-a a-g")
    zones = (network.get_zone("a"),) if with_zone else ()
    connections = (network.connections[0],) if with_connection else ()

    assert Bottleneck(1, zones, connections).limits_flow is expected


# --- limit ------------------------------------------------------------


@pytest.mark.parametrize("limit", [0, -1])
def test_limit_below_one_is_rejected(
    make_network: MakeNetwork, limit: int
) -> None:
    """ZF03: ValueError naming the limit; 1 is the smallest allowed."""
    network = make_network("s-g")

    with pytest.raises(ValueError, match=str(limit)):
        ZoneFlowGraph(network, limit)

    ZoneFlowGraph(network, 1)


# --- what the cut is made of ------------------------------------------


def test_connection_is_the_bottleneck(make_network: MakeNetwork) -> None:
    """ZF04: s-a and a-g are both 1 wide; the one nearer the start wins."""
    network = make_network("s-a a-g", capacity={"a": 5})

    assert show(solve_both_ways(network, 5)) == (1, [], ["s-a"], True)


def test_zone_is_the_bottleneck(make_network: MakeNetwork) -> None:
    """ZF05: the arc inside a (2) is the cut and comes back as zone a."""
    network = make_network(
        "s-a a-g", capacity={"a": 2}, links={"s-a": 3, "a-g": 3}
    )

    assert show(solve_both_ways(network, 5)) == (2, ["a"], [], True)


@pytest.mark.parametrize(
    ("links", "expected"),
    [
        pytest.param(
            {"s-a": 2, "a-b": 2, "b-g": 2}, (2, [], ["s-a"], True),
            id="connection-first",
        ),
        pytest.param(
            {"s-a": 3, "a-b": 2, "b-g": 2}, (2, ["a"], [], True),
            id="zone-next",
        ),
    ],
)
def test_cut_closest_to_the_start(
    make_network: MakeNetwork, links: dict[str, int], expected: Shown
) -> None:
    """ZF06: among equal cuts, the one nearest the start is returned."""
    network = make_network(
        "s-a a-b b-g", capacity={"a": 2, "b": 2}, links=links
    )

    assert show(solve_both_ways(network, 5)) == expected


def test_start_and_end_capacity_is_ignored() -> None:
    """ZF07 a): start and end with max_drones=1 do not limit the flow."""
    network = hand_built(end_drones=1, hub_drones=2, link=3)

    assert show(solve_both_ways(network, 5)) == (2, ["a"], [], True)


def test_start_and_end_are_never_in_the_cut(
    make_network: MakeNetwork,
) -> None:
    """ZF07 b): s-g of 3 is the cut; neither end zone is listed."""
    network = make_network("s-g", links={"s-g": 3})

    assert show(solve_both_ways(network, 3)) == (3, [], ["s-g"], True)


@pytest.mark.parametrize(
    ("link", "limit", "expected"),
    [
        pytest.param(2, 5, (2, [], ["s-a"], True), id="links-narrower"),
        pytest.param(10, 4, (4, [], [], False), id="room-left"),
        pytest.param(4, 4, (4, [], ["s-a"], True), id="links-equal-limit"),
    ],
)
def test_unlimited_hub_is_never_the_bottleneck(
    link: int, limit: int, expected: Shown
) -> None:
    """ZF08: a hub without max_drones gets limit + 1 and is never cut."""
    network = hand_built(end_drones=None, hub_drones=None, link=link)

    assert show(solve_both_ways(network, limit)) == expected


# --- reaching the limit -----------------------------------------------


def test_limit_reached_with_room_to_spare(make_network: MakeNetwork) -> None:
    """ZF09: 3 could pass but 2 were asked for: no bottleneck."""
    network = make_network(
        "s-a a-g", capacity={"a": 3}, links={"s-a": 3, "a-g": 3}
    )

    assert show(solve_both_ways(network, 2)) == (2, [], [], False)


@pytest.mark.parametrize(
    ("edges", "capacity", "links", "limit", "expected"),
    [
        pytest.param(
            "s-a a-g", {"a": 3}, {"s-a": 3, "a-g": 3}, 3,
            (3, [], ["s-a"], True), id="limit-3",
        ),
        pytest.param(
            "s-a a-g", {"a": 3}, {"s-a": 3, "a-g": 3}, 4,
            (3, [], ["s-a"], True), id="limit-4",
        ),
        pytest.param("s-g", {}, {}, 1, (1, [], ["s-g"], True), id="s-g"),
    ],
)
def test_exactly_saturated_still_reports_the_cut(
    make_network: MakeNetwork,
    edges: str,
    capacity: dict[str, int],
    links: dict[str, int],
    limit: int,
    expected: Shown,
) -> None:
    """ZF10: flow == limit with nothing more to push is still a cut."""
    network = make_network(edges, capacity=capacity, links=links)

    assert show(solve_both_ways(network, limit)) == expected


# --- hops that are ignored or rejected --------------------------------


def test_blocked_zone_is_not_used(make_network: MakeNetwork) -> None:
    """ZF11: the wide way through blocked x is not counted (else 6)."""
    network = make_network(
        "s-x x-g s-a a-g",
        types={"x": X},
        capacity={"x": 5},
        links={"s-x": 5, "x-g": 5},
    )

    assert show(solve_both_ways(network, 5)) == (1, [], ["s-a"], True)


def test_self_loops_are_not_used(make_network: MakeNetwork) -> None:
    """ZF12: wide self-loops a-a and s-s carry nothing and are not cut."""
    network = make_network(
        "s-a a-a a-g s-s", links={"a-a": 9, "s-s": 9}
    )

    assert show(solve_both_ways(network, 5)) == (1, [], ["s-a"], True)


@pytest.mark.parametrize(
    ("from_zone", "to_zone"),
    [
        pytest.param("s", "nope", id="to"),
        pytest.param("nope", "a", id="from"),
        pytest.param("nope", "nope", id="both"),
    ],
)
def test_hop_with_an_unknown_zone_is_rejected(
    make_network: MakeNetwork, from_zone: str, to_zone: str
) -> None:
    """ZF13: ZoneNotFoundError, checked before self-loops; no arc is left."""
    network = make_network("s-a a-g", capacity={"a": 5})
    s_a, a_g = network.connections
    graph = ZoneFlowGraph(network, 5)

    with pytest.raises(ZoneNotFoundError) as excinfo:
        graph.add_hop(s_a, from_zone, to_zone)

    assert excinfo.value.zone_name == "nope"
    graph.add_hop(s_a, "s", "a")
    graph.add_hop(a_g, "a", "g")
    assert show(graph.solve()) == (1, [], ["s-a"], True)


def test_hop_goes_one_way_only(make_network: MakeNetwork) -> None:
    """ZF14: only the backward hops g->a and a->s: nothing reaches g."""
    network = make_network("s-a a-g", capacity={"a": 5})
    s_a, a_g = network.connections
    graph = ZoneFlowGraph(network, 5)
    graph.add_hop(a_g, "g", "a")
    graph.add_hop(s_a, "a", "s")

    assert show(graph.solve()) == (0, [], [], False)


# --- order of the results ---------------------------------------------


def test_connection_is_reported_once(make_network: MakeNetwork) -> None:
    """ZF15: two parallel s-a hops are both cut, s-a is listed once."""
    network = make_network("s-a a-g", capacity={"a": 5})
    s_a, a_g = network.connections
    graph = ZoneFlowGraph(network, 5)
    for _ in range(2):
        graph.add_hop(s_a, "s", "a")
    for _ in range(3):
        graph.add_hop(a_g, "a", "g")

    assert show(graph.solve()) == (2, [], ["s-a"], True)


def test_connections_in_declaration_order(make_network: MakeNetwork) -> None:
    """ZF16: hops added in reverse, connections listed as declared."""
    network = make_network("s-a a-g s-b b-g", capacity={"a": 5, "b": 5})
    s_a, a_g, s_b, b_g = network.connections
    graph = ZoneFlowGraph(network, 5)
    graph.add_hop(b_g, "b", "g")
    graph.add_hop(s_b, "s", "b")
    graph.add_hop(a_g, "a", "g")
    graph.add_hop(s_a, "s", "a")

    assert show(graph.solve()) == (2, [], ["s-a", "s-b"], True)


def test_zones_in_declaration_order(make_network: MakeNetwork) -> None:
    """ZF17: zones are registered s, g, b, a, so b comes before a."""
    network = make_network(
        "s-b b-g s-a a-g",
        capacity={"a": 1, "b": 1},
        links={"s-b": 3, "b-g": 3, "s-a": 3, "a-g": 3},
    )

    assert show(solve_both_ways(network, 5)) == (2, ["b", "a"], [], True)


# --- nothing reaches the end ------------------------------------------


@pytest.mark.parametrize(
    ("edges", "types"),
    [
        pytest.param("s-x x-g", {"x": X}, id="blocked"),
        pytest.param("s-a b-g", {}, id="disconnected"),
    ],
)
def test_no_drone_can_pass(
    make_network: MakeNetwork, edges: str, types: dict[str, ZoneType]
) -> None:
    """ZF18: throughput 0, an empty cut, so limits_flow is False."""
    network = make_network(edges, types=types)

    bottleneck = solve_both_ways(network, 5)

    assert bottleneck == Bottleneck(0, (), ())
    assert bottleneck.limits_flow is False


@pytest.mark.parametrize(
    ("blocked", "with_hops"),
    [
        pytest.param("s", False, id="start-no-hops"),
        pytest.param("g", True, id="end-all-hops"),
    ],
)
def test_blocked_start_or_end_gives_an_empty_result(
    make_network: MakeNetwork, blocked: str, with_hops: bool
) -> None:
    """ZF19: a blocked start or end (only built in code) gives no flow."""
    network = make_network("s-a a-g", types={blocked: X})

    if with_hops:
        bottleneck = solve_both_ways(network, 3)
    else:
        bottleneck = ZoneFlowGraph(network, 3).solve()

    assert bottleneck == Bottleneck(0, (), ())
