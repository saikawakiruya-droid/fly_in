"""Tests for droneflow.simulation.scheduler (Scheduler)."""

from typing import Callable

import pytest

from droneflow.errors import SimulationError, ZoneNotFoundError
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.simulation.scheduler import Scheduler
from droneflow.simulation.state import Move, MoveOrder, SimulationState
from droneflow.simulation.turn_resolver import TurnResolver

MakeNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]
RealScheduler = Callable[[Network], Scheduler]
Snapshot = Callable[[SimulationState], dict[str, object]]
Fmt = Callable[[list[Move]], str]

R = ZoneType.RESTRICTED
P = ZoneType.PRIORITY


# --- decision order ---------------------------------------------------


def test_single_drone_moves(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D01: one drone on a line takes its next zone."""
    network = make_network("s-a a-g")

    assert real_scheduler(network).decide_moves(place(network, 1)) == [
        MoveOrder(1, "a")
    ]


def test_closest_drone_decides_first(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D02: D2 leaves b first, so D1 can enter b in the same turn."""
    network = make_network("s-a a-b b-g")
    state = place(network, 2, at={1: "a", 2: "b"})

    assert real_scheduler(network).decide_moves(state) == [
        MoveOrder(2, "g"), MoveOrder(1, "b")
    ]


def test_distance_comes_before_priority_route(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D03: a drone in a priority zone does not jump the closer drone."""
    network = make_network("s-p p-a a-g", types={"p": P})
    state = place(network, 2, at={1: "p", 2: "a"})

    assert real_scheduler(network).decide_moves(state) == [
        MoveOrder(2, "g"), MoveOrder(1, "a")
    ]


def test_tie_broken_by_priority_zone(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D04: at the same distance, the drone in a priority zone goes first."""
    network = make_network("s-x s-y x-c y-c c-g", types={"x": P})
    state = place(network, 2, at={1: "y", 2: "x"})

    assert real_scheduler(network).decide_moves(state) == [MoveOrder(2, "c")]


def test_tie_broken_by_priority_next_hop(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D05: at the same distance, a priority next hop goes first."""
    network = make_network("s-u s-y u-p y-q p-g q-g", types={"p": P})
    state = place(network, 2, at={1: "y", 2: "u"})

    assert real_scheduler(network).decide_moves(state) == [
        MoveOrder(2, "p"), MoveOrder(1, "q")
    ]


def test_full_tie_broken_by_drone_id(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D06: same distance and priority: the smallest drone_id goes."""
    network = make_network("s-a a-g")

    assert real_scheduler(network).decide_moves(place(network, 3)) == [
        MoveOrder(1, "a")
    ]


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
    make_network: MakeNetwork,
    real_scheduler: RealScheduler,
    edges: str,
    zone: str,
    expected: bool,
) -> None:
    """D07: only the zone itself and its shortest next hop count."""
    network = make_network(edges, types={"p": P})

    assert real_scheduler(network).is_on_priority_route(zone) is expected


def test_is_on_priority_route_unknown_zone(
    make_network: MakeNetwork, real_scheduler: RealScheduler
) -> None:
    """D08: an unknown zone name raises ZoneNotFoundError."""
    network = make_network("s-a a-g")

    with pytest.raises(ZoneNotFoundError):
        real_scheduler(network).is_on_priority_route("nope")


# --- choosing a hop ---------------------------------------------------


def test_waits_instead_of_detour(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D09: D2 waits rather than take the free but longer way via b."""
    network = make_network("s-a a-g s-b b-c c-g")

    assert real_scheduler(network).decide_moves(place(network, 2)) == [
        MoveOrder(1, "a")
    ]


def test_second_hop_when_first_zone_full(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D10: once the priority hop p is full, the next drone takes n."""
    network = make_network("s-p s-n p-g n-g", types={"p": P})

    assert real_scheduler(network).decide_moves(place(network, 3)) == [
        MoveOrder(1, "p"), MoveOrder(2, "n")
    ]


def test_second_hop_when_first_link_full(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D11: a has room left, but link s-a is used, so D2 takes b."""
    network = make_network("s-a s-b a-g b-g", capacity={"a": 2})

    assert real_scheduler(network).decide_moves(place(network, 3)) == [
        MoveOrder(1, "a"), MoveOrder(2, "b")
    ]


# --- drones without orders --------------------------------------------


def test_no_order_for_drone_in_flight(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D12: D1 is in flight, so it gets no order.

    Its landing frees link s-r, so D2 departs: r holds the landed D1 and
    D2 on turn 2, which fits its capacity of 2.
    """
    network = make_network("s-r r-g", types={"r": R}, capacity={"r": 2})
    state = place(network, 2, flying={1: ("s", "r")})

    assert real_scheduler(network).decide_moves(state) == [MoveOrder(2, "r")]


def test_no_order_for_delivered_drone(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D13: a delivered drone is never ordered again."""
    network = make_network("s-a a-g")
    state = place(network, 2, at={1: "g"})

    assert real_scheduler(network).decide_moves(state) == [MoveOrder(2, "a")]


# --- restricted zones -------------------------------------------------


def test_restricted_order_names_the_zone(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D14: the order names the restricted zone, not the connection."""
    network = make_network("s-r r-g", types={"r": R})

    assert real_scheduler(network).decide_moves(place(network, 1)) == [
        MoveOrder(1, "r")
    ]


def test_restricted_end_limited_by_link_only(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D15: a restricted end zone never fills; only the link stops D4."""
    network = make_network("s-g", types={"g": R}, links={"s-g": 3})

    assert real_scheduler(network).decide_moves(place(network, 4)) == [
        MoveOrder(1, "g"), MoveOrder(2, "g"), MoveOrder(3, "g")
    ]


# --- contract ---------------------------------------------------------


def test_drone_that_cannot_reach_end_is_an_error(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D16: a drone stranded off the map raises instead of waiting."""
    network = make_network("s-a a-g", isolated=("x",))
    state = place(network, 1, at={1: "x"})

    with pytest.raises(SimulationError) as excinfo:
        real_scheduler(network).decide_moves(state)
    assert "D1" in str(excinfo.value)
    assert "'x'" in str(excinfo.value)


def test_orders_are_legal_and_state_untouched(
    make_network: MakeNetwork,
    place: Place,
    real_scheduler: RealScheduler,
    snapshot: Snapshot,
    fmt: Fmt,
) -> None:
    """D17: deciding only reads the state; the resolver accepts the orders."""
    network = make_network("s-a a-b b-g")
    state = place(network, 2, at={1: "a", 2: "b"})
    before = snapshot(state)

    orders = real_scheduler(network).decide_moves(state)

    assert snapshot(state) == before
    moves = TurnResolver(network).resolve(state, orders)
    assert fmt(moves) == "D1-b D2-g"
