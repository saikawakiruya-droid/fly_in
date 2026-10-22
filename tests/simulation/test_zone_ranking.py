"""Tests for droneflow.simulation.zone_ranking (ZoneRanking).

The ranking is built the way ``Scheduler.__init__`` builds it, from a
pathfinder, every zone's shortest next hops and a ``DetourPolicy`` over
them (``ranking_for``).
"""

from typing import Callable

import pytest

from droneflow.errors import ZoneNotFoundError
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.detour_policy import DetourPolicy
from droneflow.simulation.zone_ranking import ZoneRanking

MakeNetwork = Callable[..., Network]

P = ZoneType.PRIORITY


def ranking_for(network: Network) -> ZoneRanking:
    """Build a ZoneRanking the way ``Scheduler.__init__`` does."""
    pathfinder = Pathfinder(network)
    hops = {name: pathfinder.next_hops(name) for name in network.zones}
    return ZoneRanking(
        network, pathfinder, hops, DetourPolicy(pathfinder, hops)
    )


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
