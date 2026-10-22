"""Tests for droneflow.simulation.evictor (Evictor).

Every case builds the table, the ledger and the evictor with
``evictor_for`` for the state's next turn (turn 1, unless the state says
otherwise) and calls ``make_room(zone, first_turn, extra)``.
"""

from typing import Callable

import pytest

from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.evictor import Evictor
from droneflow.simulation.reservation_table import (
    Reservation,
    ReservationTable,
)
from droneflow.simulation.state import SimulationState
from droneflow.simulation.turn_ledger import TurnLedger

MakeNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]
EvictorFor = Callable[..., tuple[ReservationTable, TurnLedger, Evictor]]
MovesOf = Callable[[ReservationTable, int], list[Reservation]]
Rv = Reservation

R = ZoneType.RESTRICTED


def rows(
    table: ReservationTable, state: SimulationState, moves_of: MovesOf
) -> set[Rv]:
    """Return every planned move of every drone of the state."""
    return {
        move for drone_id in state.drones for move in moves_of(table, drone_id)
    }


# --- making room ------------------------------------------------------


def test_evict_into_end_zone(
    make_network: MakeNetwork,
    place: Place,
    evictor_for: EvictorFor,
    moves_of: MovesOf,
) -> None:
    """X01: the drone landing in r is planned to leave for g on turn 2."""
    network = make_network("s-r r-g", types={"r": R})
    state = place(network, 2, flying={1: ("s", "r")})
    table, ledger, evictor = evictor_for(state)
    zone_r = network.get_zone("r")
    assert ledger.has_seats(zone_r, 2) is False

    assert evictor.make_room(zone_r, 2, 1) is True
    assert moves_of(table, 1) == [Rv(1, "s", "r", 0, 1), Rv(1, "r", "g", 2, 2)]


def test_evict_into_free_normal_zone(
    make_network: MakeNetwork,
    place: Place,
    evictor_for: EvictorFor,
    moves_of: MovesOf,
) -> None:
    """X02: the occupant of r takes its next hop a, which has a seat."""
    network = make_network("s-r r-a a-g", types={"r": R})
    state = place(network, 2, at={1: "r"})
    table, _, evictor = evictor_for(state)

    assert evictor.make_room(network.get_zone("r"), 2, 1) is True
    assert rows(table, state, moves_of) == {Rv(1, "r", "a", 2, 2)}


def test_evict_recursively_through_normal_zone(
    make_network: MakeNetwork,
    place: Place,
    evictor_for: EvictorFor,
    moves_of: MovesOf,
) -> None:
    """X03: a is full, so its occupant is evicted to g first."""
    network = make_network("s-r r-a a-g", types={"r": R})
    state = place(network, 3, at={1: "r", 3: "a"})
    table, _, evictor = evictor_for(state)

    assert evictor.make_room(network.get_zone("r"), 2, 1) is True
    assert rows(table, state, moves_of) == {
        Rv(1, "r", "a", 2, 2), Rv(3, "a", "g", 2, 2)
    }


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        pytest.param(
            {1: "r1"}, {Rv(1, "r1", "r2", 2, 3)}, id="r2-free"
        ),
        pytest.param(
            {1: "r1", 3: "r2"},
            {Rv(1, "r1", "r2", 2, 3), Rv(3, "r2", "g", 3, 3)},
            id="r2-held",
        ),
    ],
)
def test_evict_into_restricted_zone(
    make_network: MakeNetwork,
    place: Place,
    evictor_for: EvictorFor,
    at: dict[int, str],
    expected: set[Rv],
    moves_of: MovesOf,
) -> None:
    """X04: entering restricted r2 needs its seat from turn 3 (t+2) on."""
    network = make_network("s-r1 r1-r2 r2-g", types={"r1": R, "r2": R})
    state = place(network, len(at) + 1, at=at)
    table, _, evictor = evictor_for(state)

    assert evictor.make_room(network.get_zone("r1"), 2, 1) is True
    assert rows(table, state, moves_of) == expected


def test_long_chain_ends(
    make_network: MakeNetwork,
    place: Place,
    evictor_for: EvictorFor,
    moves_of: MovesOf,
) -> None:
    """X05: every eviction lowers the distance, so the recursion ends."""
    network = make_network(
        "s-r1 r1-r2 r2-r3 r3-g", types={"r1": R, "r2": R, "r3": R}
    )
    state = place(network, 4, at={1: "r1", 2: "r2", 3: "r3"})
    table, _, evictor = evictor_for(state)

    assert evictor.make_room(network.get_zone("r1"), 2, 1) is True
    planned = rows(table, state, moves_of)
    assert planned == {
        Rv(1, "r1", "r2", 2, 3),
        Rv(2, "r2", "r3", 3, 4),
        Rv(3, "r3", "g", 4, 4),
    }
    pathfinder = Pathfinder(network)
    for move in planned:
        after = pathfinder.distance(move.zone)
        before = pathfinder.distance(move.from_zone)
        assert after is not None and before is not None
        assert after < before


# --- failing ----------------------------------------------------------


def test_failure_undoes_every_inner_move(
    make_network: MakeNetwork,
    place: Place,
    evictor_for: EvictorFor,
    moves_of: MovesOf,
) -> None:
    """X06: D1 (and D3 for it) fit, D2 does not: all of it is undone."""
    network = make_network("s-z z-w w-g", capacity={"z": 2, "w": 1})

    state = place(network, 4, at={1: "z", 2: "z", 3: "w"})
    table, ledger, evictor = evictor_for(state)
    mark = table.mark()
    assert evictor.make_room(network.get_zone("z"), 2, 2) is False
    assert table.mark() == mark
    assert rows(table, state, moves_of) == set()
    for name in ("w-g", "z-w"):
        link = next(c for c in network.connections if c.name == name)
        assert ledger.link_free(link, 2) is True
    assert ledger.projected("z", 2) == 2
    assert ledger.projected("w", 2) == 1

    state = place(network, 4, at={1: "z", 2: "z", 3: "w"})
    table, _, evictor = evictor_for(state)
    assert evictor.make_room(network.get_zone("z"), 2, 1) is True
    assert rows(table, state, moves_of) == {
        Rv(1, "z", "w", 2, 2), Rv(3, "w", "g", 2, 2)
    }


@pytest.mark.parametrize("case", ["leaving-later", "just-landing"])
def test_no_drone_to_evict(
    make_network: MakeNetwork,
    place: Place,
    evictor_for: EvictorFor,
    case: str,
    moves_of: MovesOf,
) -> None:
    """X07: a drone already planned to leave, or landing now, is not taken."""
    network = make_network("s-r r-g", types={"r": R})
    zone_r = network.get_zone("r")
    if case == "leaving-later":
        state = place(network, 2, at={1: "r"})
        table = ReservationTable()
        table.start_turn(state)
        table.reserve(Rv(1, "r", "g", 3, 3))
        table, _, evictor = evictor_for(state, table)
        before = moves_of(table, 1)
        assert before == [Rv(1, "r", "g", 3, 3)]

        assert evictor.make_room(zone_r, 2, 1) is False
    else:
        state = place(network, 2, flying={1: ("s", "r")})
        table, _, evictor = evictor_for(state)
        before = moves_of(table, 1)
        assert before == [Rv(1, "s", "r", 0, 1)]

        assert evictor.make_room(zone_r, 1, 1) is False
    assert moves_of(table, 1) == before
    assert moves_of(table, 2) == []


def test_room_already_there(
    make_network: MakeNetwork,
    place: Place,
    evictor_for: EvictorFor,
    moves_of: MovesOf,
) -> None:
    """X08: no eviction when the zone has a seat, or is the end zone."""
    network = make_network("s-a a-g", capacity={"a": 2})
    state = place(network, 2, at={1: "a"})
    table, _, evictor = evictor_for(state)
    zone_a = network.get_zone("a")
    assert evictor.make_room(zone_a, 2, 1) is True
    assert evictor.make_room(zone_a, 2, 0) is True
    assert rows(table, state, moves_of) == set()

    direct = make_network("s-g")
    state = place(direct, 3)
    table, _, evictor = evictor_for(state)
    assert evictor.make_room(direct.get_zone("g"), 2, 5) is True
    assert rows(table, state, moves_of) == set()


def test_next_hop_when_first_link_is_taken(
    make_network: MakeNetwork,
    place: Place,
    evictor_for: EvictorFor,
    moves_of: MovesOf,
) -> None:
    """X09: D1 takes r-a on turn 2, so D2 is evicted over r-b."""
    network = make_network(
        "s-r r-a r-b a-g b-g", types={"r": R}, capacity={"r": 2}
    )
    hops = Pathfinder(network).next_hops("r")
    assert [hop.zone.name for hop in hops] == ["a", "b"]
    state = place(network, 4, at={1: "r", 2: "r"})
    table, _, evictor = evictor_for(state)

    assert evictor.make_room(network.get_zone("r"), 2, 2) is True
    assert rows(table, state, moves_of) == {
        Rv(1, "r", "a", 2, 2), Rv(2, "r", "b", 2, 2)
    }
