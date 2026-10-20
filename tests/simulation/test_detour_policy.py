"""Tests for droneflow.simulation.detour_policy (DetourPolicy).

The policy is built the way ``Scheduler.__init__`` builds it, from a
pathfinder and every zone's shortest next hops (``policy_for``). In the
``positions`` passed to ``allowed`` the deciding drone is D1 and the
other drones are D7 to D9, so that they never mix with what D1 has been
recorded in. Whether a zone is recorded as visited is checked through
``allowed`` only (on M1: a drone that has been in r gets ``[]``, another
one ``["r"]``), never through private attributes.

M1 is ``s-a a-g s-r r-g q-g`` with r restricted: s is two turns from g,
its shortest hop is a and its detour r (total cost 3); the detour of a
and of r is s, and q has none.
"""

from typing import Callable

import pytest

from droneflow.errors import ZoneNotFoundError
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.pathfinding.pathfinder import Hop, Pathfinder
from droneflow.simulation.detour_policy import DetourPolicy
from droneflow.simulation.evictor import Position

MakeNetwork = Callable[..., Network]

R = ZoneType.RESTRICTED

M1 = "s-a a-g s-r r-g q-g"
AHEAD: dict[int, Position] = {9: ("a", 0)}


def hop_names(hops: list[Hop]) -> list[str]:
    """Return the names of the zones the hops lead to, in order."""
    return [hop.zone.name for hop in hops]


def policy_for(network: Network) -> DetourPolicy:
    """Return a policy built as ``Scheduler.__init__`` builds it."""
    pathfinder = Pathfinder(network)
    return DetourPolicy(
        pathfinder,
        {name: pathfinder.next_hops(name) for name in network.zones},
    )


def m1_policy(make_network: MakeNetwork) -> DetourPolicy:
    """Return a new policy over M1 (nothing remembered yet)."""
    return policy_for(make_network(M1, types={"r": R}))


def allowed_names(
    policy: DetourPolicy,
    drone_id: int,
    zone_name: str,
    positions: dict[int, Position],
) -> list[str]:
    """Return the zones of the detours the drone may take now."""
    return hop_names(policy.allowed(drone_id, zone_name, positions))


# --- detours ----------------------------------------------------------


def test_detours_match_the_pathfinder(make_network: MakeNetwork) -> None:
    """DP01: the cached detours are the pathfinder's detour hops."""
    network = make_network(M1, types={"r": R})
    pathfinder = Pathfinder(network)
    policy = policy_for(network)

    expected = {"s": ["r"], "a": ["s"], "r": ["s"], "q": [], "g": []}
    for name, zones in expected.items():
        assert hop_names(policy.detours(name)) == zones, name
        assert policy.detours(name) == pathfinder.detour_hops(name), name


# --- the queue condition ----------------------------------------------


def test_no_detour_when_nobody_is_ahead(make_network: MakeNetwork) -> None:
    """DP02: with nobody ahead, waiting is never slower (3 + 0 > 2 + 0)."""
    assert allowed_names(m1_policy(make_network), 1, "s", {}) == []


def test_equal_costs_allow_the_detour(make_network: MakeNetwork) -> None:
    """DP03: one drone ahead makes both sides equal (3 + 0 = 2 + 1)."""
    assert allowed_names(m1_policy(make_network), 1, "s", AHEAD) == ["r"]


@pytest.mark.parametrize(
    ("positions", "expected"),
    [
        ({9: ("a", 0), 8: ("r", 0)}, []),
        ({9: ("a", 0), 8: ("r", 1)}, []),
        ({9: ("a", 0), 8: ("a", 0), 7: ("r", 0)}, ["r"]),
    ],
    ids=["one-in-r", "one-landing-in-r", "balanced"],
)
def test_queue_at_the_detour_counts(
    make_network: MakeNetwork,
    positions: dict[int, Position],
    expected: list[str],
) -> None:
    """DP04: one more drone in r refuses (3 + 1 > 2 + 1); one more ahead
    balances it again (3 + 1 = 2 + 2)."""
    policy = m1_policy(make_network)

    assert allowed_names(policy, 1, "s", positions) == expected


@pytest.mark.parametrize(
    "positions",
    [{9: ("a", 1)}, {9: ("a", 1), 8: ("a", 1), 7: ("r", 1)}],
    ids=["landing-ahead", "landing-everywhere"],
)
def test_landing_drones_count_by_zone(
    make_network: MakeNetwork, positions: dict[int, Position]
) -> None:
    """DP05: drones are counted by zone, whatever turn they arrive."""
    assert allowed_names(m1_policy(make_network), 1, "s", positions) == [
        "r"
    ]


@pytest.mark.parametrize(
    ("positions", "expected"),
    [
        ({9: ("g", 1)}, []),
        ({9: ("a", 0), 8: ("g", 1)}, ["r"]),
    ],
    ids=["only-landing-in-g", "ahead-and-landing-in-g"],
)
def test_shared_downstream_cancels_out(
    make_network: MakeNetwork,
    positions: dict[int, Position],
    expected: list[str],
) -> None:
    """DP06: g is below both s and r, so a drone there counts on both
    sides (3 + 1 > 2 + 1, then 3 + 1 <= 2 + 2)."""
    policy = m1_policy(make_network)

    assert allowed_names(policy, 1, "s", positions) == expected


@pytest.mark.parametrize(
    "positions",
    [{9: ("s", 0)}, {9: ("q", 0)}],
    ids=["in-own-zone", "other-branch"],
)
def test_drones_off_both_routes_do_not_count(
    make_network: MakeNetwork, positions: dict[int, Position]
) -> None:
    """DP07: drones in the drone's own zone or on another branch are not
    ahead of it."""
    assert allowed_names(m1_policy(make_network), 1, "s", positions) == []


@pytest.mark.parametrize(
    ("positions", "expected"),
    [
        ({9: ("a", 0)}, ["r"]),
        ({9: ("b", 0)}, []),
        ({9: ("c", 0)}, []),
        ({9: ("a", 0), 8: ("b", 0)}, ["r"]),
    ],
    ids=["in-a", "in-merge-b", "in-c", "in-a-and-b"],
)
def test_zones_further_down_and_merges(
    make_network: MakeNetwork,
    positions: dict[int, Position],
    expected: list[str],
) -> None:
    """DP08: zones two hops down count, and a merge counts on both sides.

    ``s-a a-b b-g s-r r-b c-b`` with r restricted: s is three turns from
    g, r costs 4 in all, below s are a, b and g, below r are b and g.
    """
    network = make_network("s-a a-b b-g s-r r-b c-b", types={"r": R})
    policy = policy_for(network)
    assert hop_names(policy.detours("a")) == ["s"]
    assert hop_names(policy.detours("b")) == ["a", "c", "r"]
    assert hop_names(policy.detours("c")) == []

    assert allowed_names(policy, 1, "s", positions) == expected


@pytest.mark.parametrize(
    ("positions", "expected"),
    [({9: ("b", 0)}, ["r"]), ({9: ("y", 0)}, []), ({9: ("x", 0)}, [])],
    ids=["second-shortest-branch", "unconnected-y", "unconnected-x"],
)
def test_every_shortest_branch_counts(
    make_network: MakeNetwork,
    positions: dict[int, Position],
    expected: list[str],
) -> None:
    """DP09: a drone on any shortest branch is ahead; one on a branch not
    connected to s is not."""
    network = make_network("s-a s-b a-g b-g s-r r-g x-y y-g", types={"r": R})

    assert allowed_names(policy_for(network), 1, "s", positions) == expected


@pytest.mark.parametrize(
    ("positions", "expected"),
    [
        ({9: ("a", 0)}, ["r"]),
        ({9: ("a", 0), 8: ("a", 0)}, ["r", "b"]),
        ({9: ("a", 0), 8: ("a", 0), 7: ("c", 0)}, ["r"]),
    ],
    ids=["one-ahead", "two-ahead", "two-ahead-one-below-b"],
)
def test_allowed_detours_cheapest_first(
    make_network: MakeNetwork,
    positions: dict[int, Position],
    expected: list[str],
) -> None:
    """DP11: allowed detours come by total cost; more drones ahead allow
    longer ones.

    m's detours are r, b and s (total costs 3, 4 and 5; b is declared
    before r), and b's shortest route does not go through m.
    """
    network = make_network(
        "s-m m-b b-c c-d d-g m-a a-g m-r r-g", types={"m": R, "r": R}
    )
    policy = policy_for(network)
    assert hop_names(policy.detours("m")) == ["r", "b", "s"]

    assert allowed_names(policy, 1, "m", positions) == expected


@pytest.mark.parametrize("landing", [0, 1, 2, 3])
def test_detour_back_through_the_zone_is_never_allowed(
    make_network: MakeNetwork, landing: int
) -> None:
    """DP12: a is below s, so whatever is ahead of a is also queuing for
    s, along with the deciding drone itself."""
    positions: dict[int, Position] = {1: ("a", 0)}
    for drone_id in range(7, 7 + landing):
        positions[drone_id] = ("g", 1)

    assert allowed_names(m1_policy(make_network), 1, "a", positions) == []


@pytest.mark.parametrize(
    ("positions", "expected"),
    [
        ({9: ("a", 0)}, ["r2", "r1"]),
        ({}, []),
        ({9: ("a", 0), 8: ("r2", 0)}, ["r1"]),
        ({9: ("a", 0), 8: ("a", 0), 7: ("r2", 0)}, ["r2", "r1"]),
    ],
    ids=["both", "nobody-ahead", "r2-busy", "r2-busy-two-ahead"],
)
def test_each_detour_has_its_own_queue(
    make_network: MakeNetwork,
    positions: dict[int, Position],
    expected: list[str],
) -> None:
    """DP13: with two detours, a busy one is refused on its own."""
    network = make_network(
        "s-a a-g s-r2 r2-g s-r1 r1-g", types={"r1": R, "r2": R}
    )

    assert allowed_names(policy_for(network), 1, "s", positions) == expected


# --- edge cases -------------------------------------------------------


def test_end_and_unreachable_zones_allow_nothing(
    make_network: MakeNetwork,
) -> None:
    """DP14: no detours from the end zone or a zone cut off from it."""
    assert allowed_names(m1_policy(make_network), 1, "g", AHEAD) == []

    network = make_network("s-a a-g s-r r-g", types={"r": R}, isolated=("z",))
    policy = policy_for(network)
    assert allowed_names(policy, 1, "z", AHEAD) == []
    assert policy.detours("z") == []


def test_unknown_zone_raises(make_network: MakeNetwork) -> None:
    """DP15: detours and allowed raise ZoneNotFoundError for a bad name."""
    policy = m1_policy(make_network)

    with pytest.raises(ZoneNotFoundError):
        policy.detours("nope")
    with pytest.raises(ZoneNotFoundError):
        policy.allowed(1, "nope", {})


def test_reads_only_and_returns_new_lists(
    make_network: MakeNetwork,
) -> None:
    """DP16: positions are left as they were, and clearing a returned
    list does not change the next answer."""
    policy = m1_policy(make_network)
    positions: dict[int, Position] = {9: ("a", 0)}
    before = dict(positions)

    allowed = policy.allowed(1, "s", positions)
    assert positions == before
    allowed.clear()
    policy.detours("s").clear()

    assert allowed_names(policy, 1, "s", positions) == ["r"]
    assert hop_names(policy.detours("s")) == ["r"]


# --- remembered zones -------------------------------------------------


def test_never_back_into_a_visited_zone(make_network: MakeNetwork) -> None:
    """DP10: a drone never detours into a zone it has been in.

    The record is per drone, the turns reported add up, and the zone a
    drone is landing in counts as visited.
    """
    policy = m1_policy(make_network)
    assert allowed_names(policy, 1, "s", AHEAD) == ["r"]
    assert allowed_names(policy, 2, "s", AHEAD) == ["r"]

    policy.remember(1, {1: ("r", 0), 2: ("s", 0)})
    assert allowed_names(policy, 1, "s", AHEAD) == []
    assert allowed_names(policy, 2, "s", AHEAD) == ["r"]

    policy.remember(2, {1: ("s", 1)})
    assert allowed_names(policy, 1, "s", AHEAD) == []

    landing = m1_policy(make_network)
    landing.remember(1, {3: ("r", 1)})
    assert allowed_names(landing, 3, "s", AHEAD) == []
    assert allowed_names(landing, 1, "s", AHEAD) == ["r"]


def test_reporting_a_turn_again_replaces_it(
    make_network: MakeNetwork,
) -> None:
    """DP17: a turn reported again replaces what it said before, and only
    that turn: earlier turns stay."""
    policy = m1_policy(make_network)
    policy.remember(1, {1: ("s", 0)})
    policy.remember(2, {1: ("r", 1)})
    assert allowed_names(policy, 1, "s", AHEAD) == []

    policy.remember(2, {1: ("s", 1)})
    assert allowed_names(policy, 1, "s", AHEAD) == ["r"]
    policy.remember(2, {1: ("s", 1)})
    assert allowed_names(policy, 1, "s", AHEAD) == ["r"]

    earlier = m1_policy(make_network)
    earlier.remember(1, {1: ("r", 0)})
    earlier.remember(2, {1: ("s", 1)})
    earlier.remember(2, {})
    assert allowed_names(earlier, 1, "s", AHEAD) == []


def test_reporting_an_earlier_turn_drops_later_ones(
    make_network: MakeNetwork,
) -> None:
    """DP18: reporting an earlier turn drops every later turn, even when
    the turns reported skip some numbers."""
    policy = m1_policy(make_network)
    policy.remember(1, {1: ("s", 0)})
    policy.remember(2, {1: ("r", 1)})
    policy.remember(3, {2: ("r", 2)})
    assert allowed_names(policy, 1, "s", AHEAD) == []
    assert allowed_names(policy, 2, "s", AHEAD) == []

    policy.remember(2, {1: ("s", 1), 2: ("s", 1)})
    assert allowed_names(policy, 1, "s", AHEAD) == ["r"]
    assert allowed_names(policy, 2, "s", AHEAD) == ["r"]

    policy.remember(1, {})
    assert allowed_names(policy, 1, "s", AHEAD) == ["r"]
    assert allowed_names(policy, 2, "s", AHEAD) == ["r"]

    skipped = m1_policy(make_network)
    skipped.remember(5, {1: ("r", 0)})
    skipped.remember(3, {2: ("r", 0)})
    assert allowed_names(skipped, 1, "s", AHEAD) == ["r"]
    assert allowed_names(skipped, 2, "s", AHEAD) == []
