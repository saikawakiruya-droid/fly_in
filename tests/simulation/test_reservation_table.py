"""Tests for droneflow.simulation.reservation_table (ReservationTable)."""

from typing import Callable

from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.simulation.reservation_table import (
    Reservation,
    ReservationTable,
)
from droneflow.simulation.state import SimulationState

MakeNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]
Rv = Reservation

R = ZoneType.RESTRICTED


def assert_empty(table: ReservationTable, *drone_ids: int) -> None:
    """Check that the drones have no planned move and nothing is left."""
    for drone_id in drone_ids:
        assert table.planned(drone_id) == []
    assert table.last_turn() == 0


# --- counting ---------------------------------------------------------


def test_reserve_counts_an_ordinary_move() -> None:
    """Q01: entering, leaving and due, with due in drone_id order."""
    table = ReservationTable()
    table.reserve(Rv(3, "a", "g", 2, 2))
    table.reserve(Rv(1, "b", "g", 2, 2))

    assert table.entering("g", 2) == 2
    assert table.entering("g", 3) == 0
    assert table.leaving("a", 2) == 1
    assert table.leaving("b", 2) == 1
    assert table.leaving("a", 1) == 0
    assert [move.drone_id for move in table.due(2)] == [1, 3]
    assert table.due(1) == []
    assert table.last_turn() == 2


def test_reserve_counts_a_restricted_move() -> None:
    """Q02: the drone leaves on depart_turn and enters on arrive_turn."""
    table = ReservationTable()
    move = Rv(1, "s", "r", 2, 3)
    table.reserve(move)

    assert table.entering("r", 2) == 0
    assert table.entering("r", 3) == 1
    assert table.leaving("s", 2) == 1
    assert table.leaving("s", 3) == 0
    assert table.due(2) == [move]
    assert table.due(3) == []
    assert table.last_turn() == 3


def test_drone_with_two_moves_and_remove() -> None:
    """Q03: planned is by depart_turn; remove takes every move away."""
    table = ReservationTable()
    later = Rv(1, "r", "g", 3, 3)
    first = Rv(1, "s", "r", 1, 2)
    table.reserve(later)
    table.reserve(first)

    assert table.planned(1) == [first, later]
    removed = table.remove(1)
    assert sorted(removed, key=lambda r: r.depart_turn) == [first, later]
    assert table.planned(1) == []
    assert table.entering("r", 2) == 0
    assert table.leaving("r", 3) == 0
    assert table.due(3) == []
    assert table.last_turn() == 0
    assert table.remove(1) == []
    assert table.remove(9) == []


# --- undo -------------------------------------------------------------


def test_rollback_undoes_reserves_in_nested_attempts() -> None:
    """Q04: an inner rollback keeps the outer attempt's moves."""
    table = ReservationTable()
    x = Rv(1, "s", "r", 1, 2)
    y = Rv(1, "r", "g", 3, 3)
    m1 = table.mark()
    table.reserve(x)
    m2 = table.mark()
    table.reserve(y)
    table.reserve(Rv(2, "a", "b", 4, 4))

    table.rollback(m2)
    assert table.planned(1) == [x]
    assert table.planned(2) == []

    table.rollback(m1)
    assert_empty(table, 1, 2)
    assert table.mark() == m1

    table.rollback(m1)
    assert_empty(table, 1, 2)


def test_rollback_undoes_a_remove() -> None:
    """Q05: a move removed for a try comes back on rollback."""
    table = ReservationTable()
    x = Rv(1, "s", "r", 1, 2)
    table.reserve(x)
    mark = table.mark()
    table.remove(1)

    table.rollback(mark)

    assert table.planned(1) == [x]
    assert table.entering("r", 2) == 1


def test_clear_forgets_moves_and_undo_log() -> None:
    """Q06: clear empties the table; nothing comes back on rollback."""
    table = ReservationTable()
    table.reserve(Rv(1, "s", "r", 1, 2))
    table.reserve(Rv(1, "r", "g", 3, 3))

    table.clear()
    assert_empty(table, 1)
    assert table.mark() == 0

    table.rollback(0)
    assert_empty(table, 1)


# --- start_turn -------------------------------------------------------


def test_start_turn_loads_landings(
    make_network: MakeNetwork, place: Place
) -> None:
    """Q07: a drone in flight becomes a landing, not logged for undo."""
    network = make_network("s-r r-g", types={"r": R})
    state = place(network, 2, flying={1: ("s", "r")})
    table = ReservationTable()

    table.start_turn(state)

    assert table.planned(1) == [Rv(1, "s", "r", 0, 1)]
    assert table.entering("r", 1) == 1
    assert table.mark() == 0


def test_start_turn_twice_loads_one_landing(
    make_network: MakeNetwork, place: Place
) -> None:
    """Q08: the landing is replaced, not counted twice."""
    network = make_network("s-r r-g", types={"r": R})
    state = place(network, 2, flying={1: ("s", "r")})
    table = ReservationTable()

    table.start_turn(state)
    table.start_turn(state)

    assert table.entering("r", 1) == 1
    assert len(table.planned(1)) == 1


def test_start_turn_drops_played_and_stale_moves(
    make_network: MakeNetwork, place: Place
) -> None:
    """Q09: moves already played or whose drone left are forgotten."""
    network = make_network("s-a a-b b-g", capacity={"a": 2, "b": 2})
    state = place(network, 3, at={1: "a", 2: "a", 3: "b"})
    state.turn_number = 2
    table = ReservationTable()
    keep = Rv(1, "a", "b", 4, 4)
    table.reserve(keep)
    table.reserve(Rv(2, "a", "b", 2, 2))  # departed on turn 2: played
    table.reserve(Rv(3, "a", "b", 5, 5))  # D3 is not in a: stale

    table.start_turn(state)

    assert table.planned(1) == [keep]
    assert table.planned(2) == []
    assert table.planned(3) == []
    assert table.mark() == 0
    table.rollback(0)
    assert table.planned(1) == [keep]

    state.enter_zone(1, "g")
    table.start_turn(state)
    assert table.planned(1) == []

    line = make_network("s-a a-g")
    current = ReservationTable()
    due_now = Rv(1, "a", "g", 1, 1)
    current.reserve(due_now)
    current.start_turn(place(line, 1, at={1: "a"}))
    assert current.due(1) == [due_now]


def test_eviction_of_landing_drone_is_kept(
    make_network: MakeNetwork, place: Place
) -> None:
    """Q10: a drone landing in r keeps its planned move out of r."""
    network = make_network("s-r r-g", types={"r": R})
    state = place(network, 2, flying={1: ("s", "r")})
    table = ReservationTable()
    table.start_turn(state)
    table.reserve(Rv(1, "r", "g", 2, 2))

    table.start_turn(state)

    assert [(m.from_zone, m.depart_turn) for m in table.planned(1)] == [
        ("s", 0), ("r", 2)
    ]
