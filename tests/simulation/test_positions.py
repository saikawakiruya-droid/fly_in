"""Tests for droneflow.simulation.positions (Position, PositionBoard).

The board tells where every drone will be as a turn's moves are decided:
``drones_in`` lists the drones of a zone lowest number first (a new list
each time), ``zone_by_drone`` returns a new dict, and ``count_in`` adds
up the zones it is given (callers pass a set). ``from_state`` puts a
standing drone in its zone from the turn just played and a drone in
flight in the zone it lands in from the next turn; delivered drones are
left out.
"""

from typing import Callable

import pytest

from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.simulation.positions import Position, PositionBoard
from droneflow.simulation.state import SimulationState

MakeNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]

R = ZoneType.RESTRICTED


def pb02_board() -> PositionBoard:
    """Return the PB02 board: D3 and D1 in a since 0, D2 in b since 1."""
    board = PositionBoard()
    board.place(3, "a", 0)
    board.place(1, "a", 0)
    board.place(2, "b", 1)
    return board


def test_empty_board() -> None:
    """PB01: a new board holds nothing; ``where`` raises KeyError."""
    board = PositionBoard()

    assert board.zone_by_drone() == {}
    assert board.drones_in("a") == []
    assert board.count_in(["a"]) == 0
    with pytest.raises(KeyError):
        board.where(1)


def test_place_lists_drones_lowest_number_first() -> None:
    """PB02: drones of a zone come by number, not by placing order, and a
    Position is a NamedTuple (it compares with a tuple)."""
    board = pb02_board()

    assert board.drones_in("a") == [1, 3]
    assert board.drones_in("b") == [2]
    assert board.where(3) == Position("a", 0)
    assert board.where(3) == ("a", 0)
    assert board.where(2).zone == "b"
    assert board.where(2).since_turn == 1


def test_moving_to_another_zone_leaves_the_old_one() -> None:
    """PB03: a drone placed in another zone is no longer counted in the
    zone it left."""
    board = pb02_board()

    board.place(3, "b", 2)

    assert board.drones_in("a") == [1]
    assert board.drones_in("b") == [2, 3]
    assert board.where(3) == ("b", 2)
    assert board.zone_by_drone() == {1: "a", 2: "b", 3: "b"}


def test_placing_again_in_the_same_zone_updates_the_turn() -> None:
    """PB04: only the turn changes; the zone still holds two drones."""
    board = pb02_board()
    board.place(3, "b", 2)

    board.place(3, "b", 5)

    assert board.drones_in("b") == [2, 3]
    assert board.count_in(["b"]) == 2
    assert board.where(3) == ("b", 5)


def test_count_in_adds_up_the_zones() -> None:
    """PB05: the drones of a set of zones together; unknown zones hold
    none."""
    board = pb02_board()

    assert board.count_in({"a", "b"}) == 3
    assert board.count_in(set()) == 0
    assert board.count_in({"zz"}) == 0


def test_returned_values_are_copies() -> None:
    """PB06: changing what the board returned does not change the board."""
    board = pb02_board()

    board.drones_in("a").append(99)
    board.zone_by_drone()[1] = "x"

    assert board.drones_in("a") == [1, 3]
    assert board.zone_by_drone()[1] == "a"


def test_from_state(make_network: MakeNetwork, place: Place) -> None:
    """PB07: standing drones since the turn played, drones in flight in
    their landing zone from the next turn, delivered drones left out."""
    network = make_network("s-a a-r r-g", types={"r": R}, capacity={"a": 3})
    state = place(network, 4, at={1: "a", 2: "g"}, flying={3: ("a", "r")})
    state.turn_number = 2

    board = PositionBoard.from_state(state)

    assert board.zone_by_drone() == {1: "a", 3: "r", 4: "s"}
    assert board.where(1) == ("a", 2)
    assert board.where(3) == ("r", 3)
    assert board.where(4) == ("s", 2)
