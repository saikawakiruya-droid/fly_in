"""Tests for droneflow.simulation.turn_resolver (TurnResolver)."""

from typing import Callable

import pytest

from droneflow.errors import SimulationError
from droneflow.models.drone import DroneStatus
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.simulation.state import Move, MoveOrder, SimulationState
from droneflow.simulation.turn_resolver import TurnResolver

MakeNetwork = Callable[..., Network]
Fmt = Callable[[list[Move]], str]
Snapshot = Callable[[SimulationState], dict[str, object]]

R = ZoneType.RESTRICTED
X = ZoneType.BLOCKED


def prepare(
    network: Network, nb_drones: int
) -> tuple[SimulationState, TurnResolver]:
    """Return a fresh state and a resolver for the network."""
    return SimulationState(network, nb_drones), TurnResolver(network)


# --- basics -----------------------------------------------------------


def test_single_move(make_network: MakeNetwork, fmt: Fmt) -> None:
    """T01: a legal order becomes a Move and the turn advances."""
    state, resolver = prepare(make_network("s-a a-g"), 1)
    moves = resolver.resolve(state, [MoveOrder(1, "a")])

    assert moves == [Move(1, "a")]
    assert fmt(moves) == "D1-a"
    assert state.turn_number == 1
    assert state.drones[1].current_zone == "a"


def test_no_orders_is_an_empty_turn(make_network: MakeNetwork) -> None:
    """T02: the resolver returns [] for no orders; the engine judges it."""
    state, resolver = prepare(make_network("s-a a-g"), 1)

    assert resolver.resolve(state, []) == []
    assert state.turn_number == 1


def test_moves_are_in_drone_id_order(
    make_network: MakeNetwork, fmt: Fmt
) -> None:
    """T03a: moves come out in drone_id order, not order of the orders."""
    state, resolver = prepare(make_network("s-a s-b a-g b-g"), 2)
    moves = resolver.resolve(state, [MoveOrder(2, "b"), MoveOrder(1, "a")])

    assert fmt(moves) == "D1-a D2-b"


def test_landings_and_orders_are_merged_in_id_order(
    make_network: MakeNetwork, fmt: Fmt
) -> None:
    """T03b: an automatic landing sorts among ordered moves by drone_id."""
    network = make_network("s-r r-g s-a a-g", types={"r": R})
    state, resolver = prepare(network, 2)
    connection = network.connection_between("s", "r")
    assert connection is not None
    state.enter_transit(2, connection, "r")

    moves = resolver.resolve(state, [MoveOrder(1, "a")])

    assert fmt(moves) == "D1-a D2-r"


# --- zone capacity ----------------------------------------------------


def test_two_drones_into_capacity_one_zone(
    make_network: MakeNetwork,
) -> None:
    """T04: zone capacity is enforced (the link has room for both)."""
    network = make_network("s-a a-g", links={"s-a": 2})
    state, resolver = prepare(network, 2)

    with pytest.raises(SimulationError, match="zone 'a'"):
        resolver.resolve(state, [MoveOrder(1, "a"), MoveOrder(2, "a")])


def test_filling_zone_exactly_to_capacity(
    make_network: MakeNetwork, fmt: Fmt
) -> None:
    """T05: reaching max_drones exactly is legal."""
    network = make_network("s-a a-g", capacity={"a": 2}, links={"s-a": 2})
    state, resolver = prepare(network, 2)
    moves = resolver.resolve(state, [MoveOrder(1, "a"), MoveOrder(2, "a")])

    assert fmt(moves) == "D1-a D2-a"
    assert state.occupancy("a") == 2


def test_entering_zone_freed_in_same_turn(
    make_network: MakeNetwork, fmt: Fmt
) -> None:
    """T06: a drone may enter a zone another drone leaves this turn."""
    state, resolver = prepare(make_network("s-a a-b b-g"), 2)
    state.enter_zone(1, "a")
    moves = resolver.resolve(state, [MoveOrder(1, "b"), MoveOrder(2, "a")])

    assert fmt(moves) == "D1-b D2-a"


def test_three_drone_rotation(make_network: MakeNetwork, fmt: Fmt) -> None:
    """T07: a full cycle is legal because the final loads fit."""
    state, resolver = prepare(make_network("s-a a-b b-c c-a c-g"), 3)
    state.enter_zone(1, "a")
    state.enter_zone(2, "b")
    state.enter_zone(3, "c")
    moves = resolver.resolve(
        state, [MoveOrder(1, "b"), MoveOrder(2, "c"), MoveOrder(3, "a")]
    )

    assert fmt(moves) == "D1-b D2-c D3-a"
    for name in ("a", "b", "c"):
        assert state.occupancy(name) == 1


def test_end_has_no_capacity_limit(
    make_network: MakeNetwork, fmt: Fmt
) -> None:
    """T08a: any number of drones may enter the end zone together."""
    network = make_network("s-a s-g a-g", links={"s-g": 5})
    state, resolver = prepare(network, 5)
    moves = resolver.resolve(state, [MoveOrder(i, "g") for i in range(1, 6)])

    assert fmt(moves) == "D1-g D2-g D3-g D4-g D5-g"
    assert state.is_complete is True


def test_start_has_no_capacity_limit(make_network: MakeNetwork) -> None:
    """T08b: a drone may return to a start zone holding other drones."""
    network = make_network("s-a s-g a-g", links={"s-g": 5})
    state, resolver = prepare(network, 5)
    state.enter_zone(1, "a")
    resolver.resolve(state, [MoveOrder(1, "s")])

    assert state.occupancy("s") == 5


# --- connection capacity ----------------------------------------------


@pytest.mark.parametrize("link_capacity", [1, 2])
def test_two_drones_on_one_connection(
    make_network: MakeNetwork, fmt: Fmt, link_capacity: int
) -> None:
    """T09: connection capacity is enforced (the zone has room for both)."""
    network = make_network(
        "s-a a-g", capacity={"a": 2}, links={"s-a": link_capacity}
    )
    state, resolver = prepare(network, 2)
    orders = [MoveOrder(1, "a"), MoveOrder(2, "a")]

    if link_capacity == 1:
        with pytest.raises(SimulationError, match="connection 's-a'"):
            resolver.resolve(state, orders)
    else:
        assert fmt(resolver.resolve(state, orders)) == "D1-a D2-a"


@pytest.mark.parametrize("link_capacity", [1, 2])
def test_swap_shares_connection_capacity(
    make_network: MakeNetwork, fmt: Fmt, link_capacity: int
) -> None:
    """T10: both directions count against the same connection capacity."""
    network = make_network("s-a a-b b-g", links={"a-b": link_capacity})
    state, resolver = prepare(network, 2)
    state.enter_zone(1, "a")
    state.enter_zone(2, "b")
    orders = [MoveOrder(1, "b"), MoveOrder(2, "a")]

    if link_capacity == 1:
        with pytest.raises(SimulationError, match="connection 'a-b'"):
            resolver.resolve(state, orders)
    else:
        assert fmt(resolver.resolve(state, orders)) == "D1-b D2-a"


# --- restricted zones -------------------------------------------------


def test_restricted_move_takes_two_turns(
    make_network: MakeNetwork, fmt: Fmt
) -> None:
    """T11: connection name on take-off, zone name on automatic landing."""
    state, resolver = prepare(make_network("s-r r-g", types={"r": R}), 1)
    drone = state.drones[1]

    assert fmt(resolver.resolve(state, [MoveOrder(1, "r")])) == "D1-s-r"
    assert drone.status is DroneStatus.IN_TRANSIT

    assert fmt(resolver.resolve(state, [])) == "D1-r"
    assert drone.status is DroneStatus.AT_ZONE
    assert drone.current_zone == "r"

    assert fmt(resolver.resolve(state, [MoveOrder(1, "g")])) == "D1-g"
    assert drone.status is DroneStatus.DELIVERED


def test_connection_is_printed_as_declared(
    make_network: MakeNetwork, fmt: Fmt
) -> None:
    """T12: the connection name keeps the declared order, not the heading."""
    state, resolver = prepare(make_network("r-s r-g", types={"r": R}), 1)

    assert fmt(resolver.resolve(state, [MoveOrder(1, "r")])) == "D1-r-s"


def test_reserved_restricted_zone_is_full(
    make_network: MakeNetwork,
) -> None:
    """T13: the reservation fills the zone before the drone lands."""
    network = make_network("s-r r-g", types={"r": R}, links={"s-r": 2})
    state, resolver = prepare(network, 2)
    resolver.resolve(state, [MoveOrder(1, "r")])

    with pytest.raises(SimulationError, match="zone 'r'"):
        resolver.resolve(state, [MoveOrder(2, "r")])


@pytest.mark.parametrize("link_capacity", [1, 2])
def test_landing_still_uses_the_connection(
    make_network: MakeNetwork, fmt: Fmt, link_capacity: int
) -> None:
    """T14: a flight occupies its connection on the landing turn too."""
    network = make_network(
        "s-r r-g",
        types={"r": R},
        capacity={"r": 2},
        links={"s-r": link_capacity},
    )
    state, resolver = prepare(network, 2)
    resolver.resolve(state, [MoveOrder(1, "r")])

    if link_capacity == 1:
        with pytest.raises(SimulationError, match="connection 's-r'"):
            resolver.resolve(state, [MoveOrder(2, "r")])
    else:
        moves = resolver.resolve(state, [MoveOrder(2, "r")])
        assert fmt(moves) == "D1-r D2-s-r"


def test_order_to_drone_in_flight(make_network: MakeNetwork) -> None:
    """T15: a drone in flight cannot take orders."""
    state, resolver = prepare(make_network("s-r r-g", types={"r": R}), 1)
    resolver.resolve(state, [MoveOrder(1, "r")])

    with pytest.raises(SimulationError, match="in flight"):
        resolver.resolve(state, [MoveOrder(1, "r")])
    assert state.drones[1].status is DroneStatus.IN_TRANSIT


def test_departure_frees_room_for_reservation(
    make_network: MakeNetwork, fmt: Fmt
) -> None:
    """T16: reservations are also judged on the turn's final load."""
    network = make_network(
        "s-r r-g", types={"r": R}, links={"s-r": 2, "r-g": 1}
    )
    state, resolver = prepare(network, 2)
    state.enter_zone(1, "r")
    moves = resolver.resolve(state, [MoveOrder(1, "g"), MoveOrder(2, "r")])

    assert fmt(moves) == "D1-g D2-s-r"
    assert state.reserved("r") == 1
    assert state.occupancy("r") == 0


def test_restricted_goal(make_network: MakeNetwork, fmt: Fmt) -> None:
    """T17: a restricted end is unlimited and delivers on landing."""
    network = make_network("s-g", types={"g": R}, links={"s-g": 3})
    state, resolver = prepare(network, 3)

    first = resolver.resolve(state, [MoveOrder(i, "g") for i in (1, 2, 3)])
    assert fmt(first) == "D1-s-g D2-s-g D3-s-g"
    assert fmt(resolver.resolve(state, [])) == "D1-g D2-g D3-g"
    assert state.is_complete is True
    assert state.reserved("g") == 0


# --- order validity and unchanged state -------------------------------


@pytest.mark.parametrize(
    ("orders", "message"),
    [
        pytest.param(
            [MoveOrder(7, "a")], "does not exist", id="unknown-drone"
        ),
        pytest.param(
            [MoveOrder(1, "zz")], "unknown zone 'zz'", id="unknown-zone"
        ),
        pytest.param(
            [MoveOrder(1, "b")], "not connected", id="not-adjacent"
        ),
        pytest.param(
            [MoveOrder(1, "x")], "blocked zone 'x'", id="blocked"
        ),
        pytest.param(
            [MoveOrder(1, "a"), MoveOrder(1, "g")],
            "two orders",
            id="two-orders",
        ),
        pytest.param([MoveOrder(1, "s")], "already is", id="current-zone"),
    ],
)
def test_invalid_orders(
    make_network: MakeNetwork, orders: list[MoveOrder], message: str
) -> None:
    """T18: every invalid order is a SimulationError, never another type."""
    network = make_network(
        "s-a a-b b-g s-x s-g", types={"x": X}, links={"s-a": 2}
    )
    state, resolver = prepare(network, 2)

    with pytest.raises(SimulationError, match=message):
        resolver.resolve(state, orders)


def test_order_to_delivered_drone(make_network: MakeNetwork) -> None:
    """T19: a delivered drone cannot take orders."""
    state, resolver = prepare(make_network("s-g"), 2)
    resolver.resolve(state, [MoveOrder(1, "g")])

    with pytest.raises(SimulationError, match="already delivered"):
        resolver.resolve(state, [MoveOrder(1, "g")])


def test_delivered_drones_are_not_printed(
    make_network: MakeNetwork, fmt: Fmt
) -> None:
    """T20: delivered drones drop out of the output and the end's count."""
    state, resolver = prepare(make_network("s-a a-g s-g"), 2)
    resolver.resolve(state, [MoveOrder(1, "g"), MoveOrder(2, "a")])

    assert fmt(resolver.resolve(state, [MoveOrder(2, "g")])) == "D2-g"
    assert state.occupancy("g") == 0


def legal_then_unknown_drone(
    make_network: MakeNetwork,
) -> tuple[SimulationState, TurnResolver, list[MoveOrder]]:
    """T21a: a legal first order followed by an unknown drone."""
    state, resolver = prepare(make_network("s-a a-g"), 2)
    return state, resolver, [MoveOrder(1, "a"), MoveOrder(7, "a")]


def landing_then_unknown_zone(
    make_network: MakeNetwork,
) -> tuple[SimulationState, TurnResolver, list[MoveOrder]]:
    """T21b: D1 due to land, plus an order into an unknown zone."""
    state, resolver = prepare(make_network("s-r r-g", types={"r": R}), 2)
    resolver.resolve(state, [MoveOrder(1, "r")])
    return state, resolver, [MoveOrder(2, "zz")]


def swap_over_single_link(
    make_network: MakeNetwork,
) -> tuple[SimulationState, TurnResolver, list[MoveOrder]]:
    """T21c: the illegal swap of T10a."""
    state, resolver = prepare(make_network("s-a a-b b-g"), 2)
    state.enter_zone(1, "a")
    state.enter_zone(2, "b")
    return state, resolver, [MoveOrder(1, "b"), MoveOrder(2, "a")]


def into_reserved_zone(
    make_network: MakeNetwork,
) -> tuple[SimulationState, TurnResolver, list[MoveOrder]]:
    """T21d: the second turn of T13."""
    network = make_network("s-r r-g", types={"r": R}, links={"s-r": 2})
    state, resolver = prepare(network, 2)
    resolver.resolve(state, [MoveOrder(1, "r")])
    return state, resolver, [MoveOrder(2, "r")]


@pytest.mark.parametrize(
    "scenario",
    [
        legal_then_unknown_drone,
        landing_then_unknown_zone,
        swap_over_single_link,
        into_reserved_zone,
    ],
)
def test_violation_leaves_state_unchanged(
    make_network: MakeNetwork,
    snapshot: Snapshot,
    scenario: Callable[
        [MakeNetwork], tuple[SimulationState, TurnResolver, list[MoveOrder]]
    ],
) -> None:
    """T21: a rejected turn changes nothing, not even the landings."""
    state, resolver, orders = scenario(make_network)
    before = snapshot(state)

    with pytest.raises(SimulationError):
        resolver.resolve(state, orders)
    assert snapshot(state) == before


def test_simulation_continues_after_violation(
    make_network: MakeNetwork, fmt: Fmt
) -> None:
    """T22: after a rejected turn the same state plays on normally."""
    state, resolver, orders = landing_then_unknown_zone(make_network)
    with pytest.raises(SimulationError):
        resolver.resolve(state, orders)

    assert fmt(resolver.resolve(state, [])) == "D1-r"
    assert state.turn_number == 2


@pytest.mark.parametrize(
    ("edges", "zone", "types"),
    [
        pytest.param("s-a a-a a-g", "a", {}, id="normal"),
        pytest.param("s-r r-r r-g", "r", {"r": R}, id="restricted"),
    ],
)
def test_self_loop_move_is_rejected(
    make_network: MakeNetwork,
    snapshot: Snapshot,
    edges: str,
    zone: str,
    types: dict[str, ZoneType],
) -> None:
    """T23: moving along a self-loop into the current zone is refused."""
    network = make_network(edges, types=types)
    state, resolver = prepare(network, 1)
    state.enter_zone(1, zone)
    before = snapshot(state)

    with pytest.raises(SimulationError, match="already is"):
        resolver.resolve(state, [MoveOrder(1, zone)])
    assert snapshot(state) == before
    assert state.drones[1].current_zone == zone
    assert state.occupancy(zone) == 1
    assert state.turn_number == 0
    loop = network.connection_between(zone, zone)
    assert loop is not None
    assert state.link_load(loop) == 0


def test_resolve_returns_moves(make_network: MakeNetwork) -> None:
    """T24: the result is Move records, never the MoveOrders given."""
    state, resolver = prepare(make_network("s-a a-g"), 1)
    restricted_state, restricted_resolver = prepare(
        make_network("s-r r-g", types={"r": R}), 1
    )
    turns = [
        resolver.resolve(state, [MoveOrder(1, "a")]),
        restricted_resolver.resolve(restricted_state, [MoveOrder(1, "r")]),
        restricted_resolver.resolve(restricted_state, []),
    ]

    for moves in turns:
        assert moves
        for move in moves:
            assert isinstance(move, Move)
            assert not isinstance(move, MoveOrder)
            assert isinstance(move.destination, str)
