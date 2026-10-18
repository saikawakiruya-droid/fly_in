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


# --- planned moves and evictions (timed reservation) ------------------

# K1: r holds two drones, but only one can leave per turn (r-g).
K1_LINES = [
    "D1-s-r D2-s-r",
    "D1-r D2-r D3-s-r",
    "D1-g D3-r D4-s-r",
    "D2-g D4-r",
    "D3-g",
    "D4-g",
]
# Three restricted zones in a row: one drone departs every turn.
CHAIN_LINES = [
    "D1-s-r1",
    "D1-r1 D2-s-r1",
    "D1-r1-r2 D2-r1 D3-s-r1",
    "D1-r2 D2-r1-r2 D3-r1",
    "D1-r2-r3 D2-r2 D3-r1-r2",
    "D1-r3 D2-r2-r3 D3-r2",
    "D1-g D2-r3 D3-r2-r3",
    "D2-g D3-r3",
    "D3-g",
]


def play(
    scheduler: Scheduler,
    resolver: TurnResolver,
    state: SimulationState,
    turns: int,
) -> list[list[Move]]:
    """Decide and resolve the given number of turns; return their moves."""
    return [
        resolver.resolve(state, scheduler.decide_moves(state))
        for _ in range(turns)
    ]


def play_out(
    scheduler: Scheduler, state: SimulationState, fmt: Fmt, calls: int = 1
) -> list[str]:
    """Play until every drone is delivered; return the printed lines.

    ``decide_moves`` is called ``calls`` times per turn; every call must
    give the same orders, and the last ones are played.
    """
    resolver = TurnResolver(state.network)
    lines: list[str] = []
    while not state.is_complete:
        assert state.turn_number < 50, "not finished in 50 turns"
        orders = scheduler.decide_moves(state)
        for _ in range(calls - 1):
            again = scheduler.decide_moves(state)
            assert again == orders, f"turn {state.turn_number + 1}"
            orders = again
        lines.append(fmt(resolver.resolve(state, orders)))
    return lines


def k1_network(make_network: MakeNetwork) -> Network:
    """Return K1: s-r r-g, r restricted with room for 2, link s-r of 2."""
    return make_network(
        "s-r r-g", types={"r": R}, capacity={"r": 2}, links={"s-r": 2}
    )


def chain_network(make_network: MakeNetwork) -> Network:
    """Return three restricted zones of capacity 1 in a row."""
    return make_network(
        "s-r1 r1-r2 r2-r3 r3-g", types={"r1": R, "r2": R, "r3": R}
    )


def m7_network(make_network: MakeNetwork) -> Network:
    """Return the rule 7 network (four drones, turn 5 is the case)."""
    return make_network(
        "z0-g s-z1 z1-z0",
        types={"z0": R, "z1": R},
        capacity={"z0": 2, "z1": 1},
        links={"z0-g": 2, "s-z1": 2},
    )


def m6_network(make_network: MakeNetwork) -> Network:
    """Return the rule 6' network (six drones, turn 7 is the case)."""
    return make_network(
        "z3-z1 z4-z3 z3-z2 s-z4 z2-z4 z2-z0 z1-g z0-z1",
        types={"z3": R, "z4": R},
        links={"z3-z1": 2, "z3-z2": 2, "s-z4": 2},
    )


def test_planned_moves_come_first(
    make_network: MakeNetwork, real_scheduler: RealScheduler
) -> None:
    """D18: D3's planned move out of z1 comes before D1's own decision.

    By distance alone D1 (one hop from g) would be first.
    """
    network = m7_network(make_network)
    scheduler = real_scheduler(network)
    state = SimulationState(network, 4)
    play(scheduler, TurnResolver(network), state, 4)

    assert scheduler.decide_moves(state) == [
        MoveOrder(3, "z0"), MoveOrder(1, "g")
    ]


def test_drone_with_planned_eviction_may_move_earlier(
    make_network: MakeNetwork,
    real_scheduler: RealScheduler,
    fmt: Fmt,
) -> None:
    """D19: D1, planned to leave z0 on turn 6, leaves on turn 5 instead.

    Its planned move is dropped, so turn 6 has no order for it.
    """
    network = m7_network(make_network)
    scheduler = real_scheduler(network)
    resolver = TurnResolver(network)
    state = SimulationState(network, 4)
    play(scheduler, resolver, state, 4)

    orders = scheduler.decide_moves(state)
    assert MoveOrder(1, "g") in orders
    moves = resolver.resolve(state, orders)
    assert fmt(moves) == "D1-g D2-z0 D3-z1-z0 D4-z1"

    orders = scheduler.decide_moves(state)
    assert orders == [MoveOrder(2, "g"), MoveOrder(4, "z0")]
    resolver.resolve(state, orders)


def test_departure_to_restricted_plans_an_eviction(
    make_network: MakeNetwork,
    place: Place,
    real_scheduler: RealScheduler,
    snapshot: Snapshot,
    fmt: Fmt,
) -> None:
    """D20: D2 takes off toward r, and D1 is planned to leave r for it."""
    network = make_network("s-r r-g", types={"r": R})
    scheduler = real_scheduler(network)
    resolver = TurnResolver(network)
    state = place(network, 2, flying={1: ("s", "r")})
    before = snapshot(state)

    orders = scheduler.decide_moves(state)
    assert orders == [MoveOrder(2, "r")]
    assert snapshot(state) == before
    assert fmt(resolver.resolve(state, orders)) == "D1-r D2-s-r"

    orders = scheduler.decide_moves(state)
    assert orders == [MoveOrder(1, "g")]
    assert fmt(resolver.resolve(state, orders)) == "D1-g D2-r"


def test_waits_when_eviction_fails(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D21: D3 goes; D4 waits, since r-g on turn 3 is D1's (K1, turn 2)."""
    network = k1_network(make_network)
    state = place(network, 4, flying={1: ("s", "r"), 2: ("s", "r")})

    assert real_scheduler(network).decide_moves(state) == [MoveOrder(3, "r")]


def test_eviction_is_a_last_resort(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D22: D4 takes the free b rather than evict from a (its first hop).

    D5 finds no room as it is (a is full, s-b is taken by D4), so it
    evicts from a on its second try.
    """
    network = make_network(
        "s-a a-g s-b b-g",
        types={"a": R, "b": R},
        capacity={"a": 2, "b": 3},
        links={"s-a": 2},
    )
    state = place(
        network, 6, flying={1: ("s", "a"), 2: ("s", "a"), 3: ("s", "b")}
    )

    assert real_scheduler(network).decide_moves(state) == [
        MoveOrder(4, "b"), MoveOrder(5, "a")
    ]


def test_enters_a_seat_kept_for_later_and_evicts_itself(
    make_network: MakeNetwork, real_scheduler: RealScheduler
) -> None:
    """D23 (rule 6'): D3 enters z1, kept for D4 on turn 8, and is planned
    to leave it for g on turn 8."""
    network = m6_network(make_network)
    scheduler = real_scheduler(network)
    resolver = TurnResolver(network)
    state = SimulationState(network, 6)
    play(scheduler, resolver, state, 6)

    orders = scheduler.decide_moves(state)
    assert orders == [
        MoveOrder(5, "z3"), MoveOrder(2, "g"), MoveOrder(3, "z1")
    ]
    resolver.resolve(state, orders)

    assert scheduler.decide_moves(state) == [
        MoveOrder(3, "g"), MoveOrder(4, "z1"), MoveOrder(6, "z2")
    ]


def test_same_turn_again_gives_the_same_orders(
    make_network: MakeNetwork,
    place: Place,
    real_scheduler: RealScheduler,
    fmt: Fmt,
) -> None:
    """D24: deciding a turn again does not plan its evictions twice."""
    network = make_network("s-r r-g", types={"r": R})
    scheduler = real_scheduler(network)
    resolver = TurnResolver(network)
    state = place(network, 2, flying={1: ("s", "r")})

    assert scheduler.decide_moves(state) == [MoveOrder(2, "r")]
    orders = scheduler.decide_moves(state)
    assert orders == [MoveOrder(2, "r")]
    assert fmt(resolver.resolve(state, orders)) == "D1-r D2-s-r"
    orders = scheduler.decide_moves(state)
    assert orders == [MoveOrder(1, "g")]
    assert fmt(resolver.resolve(state, orders)) == "D1-g D2-r"

    k1 = k1_network(make_network)
    lines = play_out(real_scheduler(k1), SimulationState(k1, 4), fmt, 3)
    assert lines == K1_LINES
    chain = chain_network(make_network)
    lines = play_out(
        real_scheduler(chain), SimulationState(chain, 3), fmt, 3
    )
    assert lines == CHAIN_LINES


def test_new_run_starts_with_an_empty_table(
    make_network: MakeNetwork, real_scheduler: RealScheduler, fmt: Fmt
) -> None:
    """D25: a second run on the same scheduler is not affected by the
    first one's planned moves."""
    network = k1_network(make_network)
    scheduler = real_scheduler(network)

    assert play_out(scheduler, SimulationState(network, 4), fmt) == K1_LINES
    assert play_out(scheduler, SimulationState(network, 4), fmt) == K1_LINES


def test_same_turn_with_another_state_replans_from_it(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D26: the landing of the state given first does not stay planned."""
    network = make_network("s-r r-g", types={"r": R})
    scheduler = real_scheduler(network)
    scheduler.decide_moves(place(network, 2, flying={1: ("s", "r")}))

    orders = scheduler.decide_moves(place(network, 2))

    assert orders == real_scheduler(network).decide_moves(place(network, 2))
    assert orders == [MoveOrder(1, "r")]
