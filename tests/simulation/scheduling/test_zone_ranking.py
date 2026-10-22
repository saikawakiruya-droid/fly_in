"""Tests for droneflow.simulation.scheduling.zone_ranking (ZoneRanking).

The ranking is built the way ``Scheduler.__init__`` builds it, from a
pathfinder, every zone's shortest next hops and a ``DetourPolicy`` over
them (``ranking_for``). ``order`` lists the ranked zones in decision
order. The keys, in turn: distance to the end zone, then zones on the
priority route, then fewer exits (shortest hops and detours), then
declaration order (``network.zones``).
"""

from typing import Callable

import pytest

from droneflow.errors import ZoneNotFoundError
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.scheduling.detour_policy import DetourPolicy
from droneflow.simulation.scheduling.zone_ranking import ZoneRanking

MakeNetwork = Callable[..., Network]

P = ZoneType.PRIORITY
X = ZoneType.BLOCKED


def ranking_for(network: Network) -> ZoneRanking:
    """Build a ZoneRanking the way ``Scheduler.__init__`` does."""
    pathfinder = Pathfinder(network)
    hops = {name: pathfinder.next_hops(name) for name in network.zones}
    return ZoneRanking(
        network, pathfinder, hops, DetourPolicy(pathfinder, hops)
    )


def order(network: Network) -> list[str]:
    """Return the zones that have a rank, in decision order."""
    ranking = ranking_for(network)
    ranked = [
        (rank, name) for name in network.zones
        if (rank := ranking.rank(name)) is not None
    ]
    return [name for _, name in sorted(ranked)]


# --- rank -------------------------------------------------------------


def test_closest_to_the_end_first(make_network: MakeNetwork) -> None:
    """ZR01: the first key is the distance to the end zone."""
    network = make_network("s-a a-b b-g")
    ranking = ranking_for(network)

    assert order(network) == ["g", "b", "a", "s"]
    assert ranking.rank("g") == 0
    assert ranking.rank("s") == 3


def test_priority_zone_first_at_equal_distance(
    make_network: MakeNetwork,
) -> None:
    """ZR02: at the same distance a priority zone comes first."""
    network = make_network("s-x s-y x-c y-c c-g", types={"x": P})

    assert order(network) == ["g", "c", "x", "y", "s"]


def test_priority_next_hop_first_at_equal_distance(
    make_network: MakeNetwork,
) -> None:
    """ZR03: p is a priority zone itself and u's shortest next hop is p,
    so both come before their peers."""
    network = make_network("s-u s-y u-p y-q p-g q-g", types={"p": P})

    assert order(network) == ["g", "p", "q", "u", "y", "s"]


def test_fewer_exits_first(make_network: MakeNetwork) -> None:
    """ZR04: detours count as exits. At distance 1, d (2 exits) comes
    before c (g plus the detours a and b); at distance 2, b (c and d) before
    a (c, d and the detour s)."""
    network = make_network("s-a s-b a-c b-c a-d c-g d-g")

    assert order(network) == ["g", "d", "c", "b", "a", "s"]


def test_declaration_order_last(make_network: MakeNetwork) -> None:
    """ZR05: the last key is the order of ``network.zones``."""
    assert order(make_network("s-b s-a a-g b-g")) == ["g", "b", "a", "s"]
    assert order(make_network("s-a a-g s-b b-g a-b")) == ["g", "a", "b", "s"]


def test_zones_that_cannot_finish_have_no_rank(
    make_network: MakeNetwork,
) -> None:
    """ZR06: an isolated or blocked zone has no rank; an unknown name
    raises ZoneNotFoundError."""
    isolated = make_network("s-a a-g", isolated=("z",))
    assert ranking_for(isolated).rank("z") is None

    blocked = make_network("s-a a-g s-x x-g", types={"x": X})
    ranking = ranking_for(blocked)
    assert ranking.rank("x") is None
    assert order(blocked) == ["g", "a", "s"]
    with pytest.raises(ZoneNotFoundError) as excinfo:
        ranking.rank("nope")
    assert excinfo.value.zone_name == "nope"


# --- is_on_priority_route ---------------------------------------------


@pytest.mark.parametrize(
    ("edges", "zone", "expected"),
    [
        ("s-p p-g", "p", True),
        ("s-p p-g", "s", True),
        ("s-a a-p p-g", "s", False),
        ("s-a a-g s-p p-q q-g", "s", False),
        ("s-p p-g", "g", False),
    ],
    ids=[
        "in-priority-zone",
        "next-hop-priority",
        "priority-two-hops-away",
        "priority-on-detour",
        "end-zone",
    ],
)
def test_is_on_priority_route(
    make_network: MakeNetwork, edges: str, zone: str, expected: bool
) -> None:
    """ZR07 (formerly D07): only the zone itself and its shortest next hop
    count."""
    network = make_network(edges, types={"p": P})

    assert ranking_for(network).is_on_priority_route(zone) is expected


def test_is_on_priority_route_unknown_zone(make_network: MakeNetwork) -> None:
    """ZR08 (formerly D08): an unknown zone name raises ZoneNotFoundError."""
    network = make_network("s-a a-g")

    with pytest.raises(ZoneNotFoundError):
        ranking_for(network).is_on_priority_route("nope")
