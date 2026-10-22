"""Tests for droneflow.simulation.scheduler (Scheduler)."""

from typing import Callable

import pytest

from droneflow.errors import SimulationError
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.pathfinding.pathfinder import Pathfinder
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


def test_same_zone_keeps_active_drone_order(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D06: drones in the same zone keep active_drones order.

    The drone_id itself is not part of the decision order (see D35).
    """
    network = make_network("s-a a-g")

    assert real_scheduler(network).decide_moves(place(network, 3)) == [
        MoveOrder(1, "a")
    ]


# --- choosing a hop ---------------------------------------------------


def test_takes_a_sideways_detour(
    make_network: MakeNetwork,
    place: Place,
    real_scheduler: RealScheduler,
    fmt: Fmt,
) -> None:
    """D09: b is as far from g as s; D2 goes sideways there, as it costs
    no more than queuing behind D1."""
    network = make_network("s-a a-g s-b b-c c-g")

    assert real_scheduler(network).decide_moves(place(network, 2)) == [
        MoveOrder(1, "a"), MoveOrder(2, "b")
    ]
    assert play_out(real_scheduler(network), place(network, 2), fmt) == [
        "D1-a D2-b",
        "D1-g D2-c",
        "D2-g",
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


# --- detours and the zone decision order ------------------------------

# M1': s-a a-g s-r r-g, r restricted: the shortest hop of s is a and its
# detour is r. S: s-a a-g s-b b-c c-g: the detour of s is the sideways b.
M1_PRIME = "s-a a-g s-r r-g"
SIDEWAYS = "s-a a-g s-b b-c c-g"


def orders_by_turn(
    network: Network, state: SimulationState
) -> list[list[tuple[int, str]]]:
    """Play until every drone is delivered; return each turn's orders.

    One scheduler and one resolver play every turn. The orders are kept
    in the order ``decide_moves`` gave them, as ``(drone_id, zone)``.
    """
    scheduler = Scheduler(network, Pathfinder(network))
    resolver = TurnResolver(network)
    turns: list[list[tuple[int, str]]] = []
    while not state.is_complete:
        assert state.turn_number < 50, "not finished in 50 turns"
        orders = scheduler.decide_moves(state)
        turns.append([(order.drone_id, order.zone_name) for order in orders])
        resolver.resolve(state, orders)
    return turns


def test_drone_that_would_wait_takes_a_detour(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D27: D1's move into a decided this turn puts one drone ahead of
    D2, so D2 goes round by r; alone, D1 just takes a."""
    network = make_network(M1_PRIME, types={"r": R})

    assert real_scheduler(network).decide_moves(place(network, 2)) == [
        MoveOrder(1, "a"), MoveOrder(2, "r")
    ]
    assert real_scheduler(network).decide_moves(place(network, 1)) == [
        MoveOrder(1, "a")
    ]


def test_no_detour_while_a_shortest_hop_is_free(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D28: a has room for both, so D2 follows D1 although r is allowed."""
    network = make_network(
        M1_PRIME, types={"r": R}, capacity={"a": 2}, links={"s-a": 2}
    )

    assert real_scheduler(network).decide_moves(place(network, 2)) == [
        MoveOrder(1, "a"), MoveOrder(2, "a")
    ]


def test_busy_detour_is_refused(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D29: a drone queuing at the detour counts against it.

    (a) D3 finds D2 bound for r (3 + 1 > 2 + 1) and waits. (b) and (c)
    differ only in where D3 is: in b it blocks D2's detour; in g (after
    moving first) it counts on both sides, so D2 may go.
    """
    wide = make_network(
        M1_PRIME, types={"r": R}, capacity={"r": 2}, links={"s-r": 2}
    )
    assert real_scheduler(wide).decide_moves(place(wide, 3)) == [
        MoveOrder(1, "a"), MoveOrder(2, "r")
    ]

    network = make_network(SIDEWAYS)
    in_b = place(network, 3, at={3: "b"})
    assert real_scheduler(network).decide_moves(in_b) == [
        MoveOrder(1, "a"), MoveOrder(3, "c")
    ]
    in_c = place(network, 3, at={3: "c"})
    assert real_scheduler(network).decide_moves(in_c) == [
        MoveOrder(3, "g"), MoveOrder(1, "a"), MoveOrder(2, "b")
    ]


def test_detour_tries_without_eviction_first(
    make_network: MakeNetwork,
    place: Place,
    real_scheduler: RealScheduler,
    fmt: Fmt,
) -> None:
    """D30: a detour may evict (a), but one needing no eviction comes
    first (b).

    (a) D5 plans D1's eviction from r1 and goes there (6 <= 6). (b) r1
    is still allowed and declared first, yet D5 takes the free r2.
    """
    edges = "s-a a-b b-g s-r1 r1-b"
    one = make_network(edges, types={"r1": R}, capacity={"a": 2})
    two = make_network(
        f"{edges} s-r2 r2-b", types={"r1": R, "r2": R}, capacity={"a": 2}
    )
    at = {2: "a", 3: "a"}
    flying = {1: ("s", "r1")}

    assert real_scheduler(one).decide_moves(
        place(one, 5, at=at, flying=flying)
    ) == [MoveOrder(2, "b"), MoveOrder(4, "a"), MoveOrder(5, "r1")]
    assert play_out(
        real_scheduler(one), place(one, 5, at=at, flying=flying), fmt
    ) == [
        "D1-r1 D2-b D4-a D5-s-r1",
        "D1-b D2-g D5-r1",
        "D1-g D3-b",
        "D3-g D4-b",
        "D4-g D5-b",
        "D5-g",
    ]

    assert real_scheduler(two).decide_moves(
        place(two, 5, at=at, flying=flying)
    ) == [MoveOrder(2, "b"), MoveOrder(4, "a"), MoveOrder(5, "r2")]
    assert play_out(
        real_scheduler(two), place(two, 5, at=at, flying=flying), fmt
    ) == [
        "D1-r1 D2-b D4-a D5-s-r2",
        "D2-g D3-b D5-r2",
        "D3-g D4-b",
        "D1-b D4-g",
        "D1-g D5-b",
        "D5-g",
    ]


@pytest.mark.parametrize(
    ("nb_drones", "orders", "lines"),
    [
        (
            2,
            [MoveOrder(2, "t")],
            ["D1-t D2-s-t", "D1-g D2-t", "D2-g"],
        ),
        (
            3,
            [MoveOrder(2, "t"), MoveOrder(3, "r")],
            [
                "D1-t D2-s-t D3-s-r",
                "D1-g D2-t D3-r",
                "D2-g D3-b",
                "D3-g",
            ],
        ),
    ],
    ids=["two", "three"],
)
def test_shortest_eviction_comes_before_a_detour(
    make_network: MakeNetwork,
    place: Place,
    real_scheduler: RealScheduler,
    fmt: Fmt,
    nb_drones: int,
    orders: list[MoveOrder],
    lines: list[str],
) -> None:
    """D31: D2 evicts D1 from t (its shortest hop) rather than detour;
    only D3, finding t taken, goes round by r."""
    network = make_network("s-t t-g s-r r-b b-g", types={"t": R, "r": R})
    flying = {1: ("s", "t")}

    state = place(network, nb_drones, flying=flying)
    assert real_scheduler(network).decide_moves(state) == orders
    state = place(network, nb_drones, flying=flying)
    assert play_out(real_scheduler(network), state, fmt) == lines


def test_fewer_exits_decide_first(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D32: at the same distance, x (two exits) decides before y (three),
    though y is declared first: D2 takes m, D1 still has n."""
    network = make_network("s-y s-x y-m x-m y-n m-g n-g")
    state = place(network, 2, at={1: "y", 2: "x"})

    assert real_scheduler(network).decide_moves(state) == [
        MoveOrder(2, "m"), MoveOrder(1, "n")
    ]


def test_exits_include_detours(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D33: x's exits are m, r (a detour) and s, three against y's two,
    so D2 in y takes m and D1 goes round by r."""
    network = make_network("s-x s-y x-m y-m m-g x-r r-g", types={"r": R})
    state = place(network, 2, at={1: "x", 2: "y"})

    assert real_scheduler(network).decide_moves(state) == [
        MoveOrder(2, "m"), MoveOrder(1, "r")
    ]


def test_priority_route_before_fewer_exits(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D34: p (priority, three exits) decides before x (two exits).

    D2 takes m, so D1 in x waits: with exits first it would have been
    D1 to m and D2 to n.
    """
    network = make_network("s-p s-x p-m p-n x-m m-g n-g", types={"p": P})
    state = place(network, 2, at={1: "x", 2: "p"})

    assert real_scheduler(network).decide_moves(state) == [
        MoveOrder(2, "m")
    ]


def test_declaration_order_not_drone_id(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D35: on a full tie the zone declared first (y) decides first,
    whatever the drone_ids (see D06 for one zone)."""
    network = make_network("s-y s-x y-m x-m m-g")
    state = place(network, 2, at={1: "x", 2: "y"})

    assert real_scheduler(network).decide_moves(state) == [
        MoveOrder(2, "m")
    ]


def test_stranded_drone_is_an_error_with_detours(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D36: a drone in a zone that cannot reach g still raises."""
    network = make_network("s-a a-g s-r r-g x-y", types={"r": R})
    state = place(network, 2, at={1: "x"})

    with pytest.raises(SimulationError) as excinfo:
        real_scheduler(network).decide_moves(state)
    assert str(excinfo.value) == (
        "D1 is in 'x', which cannot reach the end zone"
    )


def test_detour_away_from_the_end_zone(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D37: a detour farther from g, when v's route avoids m.

    (a) Three drones are ahead of D4 in m, so it goes back to v (5 + 0
    <= 3 + 3) and on through w1, w2 and w3. (b) With one ahead it waits
    (5 > 4).
    """
    network = make_network(
        "s-m m-c1 c1-c2 c2-g m-v v-w1 w1-w2 w2-w3 w3-g",
        types={"m": R},
        capacity={"m": 2},
    )
    crowded = place(network, 4, at={1: "c1", 2: "c2", 3: "m", 4: "m"})

    turns = orders_by_turn(network, crowded)

    assert turns[0] == [(2, "g"), (1, "c2"), (3, "c1"), (4, "v")]
    assert len(turns) == 5
    assert [
        zone for orders in turns[1:] for drone_id, zone in orders
        if drone_id == 4
    ] == ["w1", "w2", "w3", "g"]

    alone = place(network, 2, at={1: "m", 2: "m"})
    assert real_scheduler(network).decide_moves(alone) == [
        MoveOrder(1, "c1")
    ]


def test_no_detour_back_into_a_visited_zone(
    make_network: MakeNetwork,
    place: Place,
    real_scheduler: RealScheduler,
    fmt: Fmt,
) -> None:
    """D38: D3 goes sideways from y to x, then never back to y.

    On turn 2 going back would meet the condition (3 + 1 <= 2 + 2), but
    D3 has been in y, so it waits.
    """
    network = make_network(
        "s-x x-y x-a a-g y-b b-g",
        capacity={"x": 2, "y": 2, "a": 2, "b": 2},
    )
    at = {2: "y", 3: "y"}

    turns = orders_by_turn(network, place(network, 3, at=at))

    assert turns[0] == [(2, "b"), (3, "x"), (1, "x")]
    assert turns[1] == [(2, "g"), (1, "a")]
    state = place(network, 3, at=at)
    assert play_out(real_scheduler(network), state, fmt) == [
        "D1-x D2-b D3-x",
        "D1-a D2-g",
        "D1-g D3-a",
        "D3-g",
    ]


def test_new_run_forgets_the_visited_zones(
    make_network: MakeNetwork, real_scheduler: RealScheduler, fmt: Fmt
) -> None:
    """D39: a second run on the same scheduler takes the same detour.

    Reporting turn 1 again drops what the first run recorded.
    """
    network = make_network(SIDEWAYS)
    scheduler = real_scheduler(network)
    lines = ["D1-a D2-b", "D1-g D2-c", "D2-g"]

    assert play_out(scheduler, SimulationState(network, 2), fmt) == lines
    assert play_out(scheduler, SimulationState(network, 2), fmt) == lines


def test_same_turn_with_another_state_forgets_its_visits(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """D40: D2 landing in r in the state given first is not remembered
    when the same turn is planned again from another state."""
    network = make_network(M1_PRIME, types={"r": R})
    scheduler = real_scheduler(network)
    first = scheduler.decide_moves(place(network, 2, flying={2: ("s", "r")}))
    assert first == [MoveOrder(1, "a")]

    orders = scheduler.decide_moves(place(network, 2))

    assert orders == real_scheduler(network).decide_moves(place(network, 2))
    assert orders == [MoveOrder(1, "a"), MoveOrder(2, "r")]


# --- drones evicted this turn are decided too -------------------------

# RV (the review's counterexample): u and v are two turns from g, w, y
# and z1 one; v is restricted (room for 1), u has room for 2 and w for 4.
# D1 and D2 stand in u, D3 to D5 in w, D6 in v.
RV_AT = {1: "u", 2: "u", 3: "w", 4: "w", 5: "w", 6: "v"}
RV_ORDERS = [
    MoveOrder(3, "g"), MoveOrder(1, "w"), MoveOrder(2, "v"), MoveOrder(6, "y")
]


def rv_network(make_network: MakeNetwork) -> Network:
    """Return RV: s-u u-w w-g u-v v-y y-g v-z1 z1-g, v restricted."""
    return make_network(
        "s-u u-w w-g u-v v-y y-g v-z1 z1-g",
        types={"v": R},
        capacity={"u": 2, "w": 4},
    )


def test_drone_evicted_this_turn_is_decided(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """RV01: D2 finds u-w taken by D1 and detours into the full v, which
    plans D6's eviction (v -> y on turn 2). D6, decided after that, drops
    the planned move and goes to y now."""
    network = rv_network(make_network)

    orders = real_scheduler(network).decide_moves(place(network, 6, at=RV_AT))

    assert orders == RV_ORDERS


def test_evicted_drone_keeps_no_planned_move(
    make_network: MakeNetwork,
    place: Place,
    real_scheduler: RealScheduler,
    fmt: Fmt,
) -> None:
    """RV02: played to the end, D6 has no planned move left on turn 2 and
    D2 lands in v."""
    network = rv_network(make_network)

    lines = play_out(real_scheduler(network), place(network, 6, at=RV_AT), fmt)
    turns = orders_by_turn(network, place(network, 6, at=RV_AT))

    assert lines == [
        "D1-w D2-u-v D3-g D6-y",
        "D1-g D2-v D6-g",
        "D2-y D4-g",
        "D2-g D5-g",
    ]
    assert turns[1] == [(1, "g"), (6, "g")]


def test_evicted_drone_same_turn_again(
    make_network: MakeNetwork, place: Place, real_scheduler: RealScheduler
) -> None:
    """RV03: deciding the RV turn twice gives the same orders both times,
    the same as a new scheduler: the dropped and the restored planned
    moves are not doubled."""
    network = rv_network(make_network)
    scheduler = real_scheduler(network)
    state = place(network, 6, at=RV_AT)

    first = scheduler.decide_moves(state)
    second = scheduler.decide_moves(state)

    assert first == RV_ORDERS
    assert second == RV_ORDERS
    assert real_scheduler(network).decide_moves(state) == RV_ORDERS
