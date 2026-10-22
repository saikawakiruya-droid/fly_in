"""Tests for droneflow.simulation.scheduling.turn_ledger (TurnLedger)."""

from typing import Callable

import pytest

from droneflow.models.connection import Connection
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.pathfinding.pathfinder import Hop
from droneflow.simulation.scheduling.reservation_table import (
    Reservation,
    ReservationTable,
)
from droneflow.simulation.state import SimulationState
from droneflow.simulation.scheduling.turn_ledger import TurnLedger

MakeNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]
MakeHop = Callable[[Network, str, str], Hop]
Snapshot = Callable[[SimulationState], dict[str, object]]
MovesOf = Callable[[ReservationTable, int], list[Reservation]]
Rv = Reservation

R = ZoneType.RESTRICTED


def has_room(ledger: TurnLedger, hop: Hop) -> bool:
    """Return whether one more drone can take ``hop`` this turn.

    The link has room this turn and the zone a seat from the turn the
    drone enters it on: the same rule as the removed
    ``TurnLedger.has_room``, and as the no-eviction check of
    ``HopTaker._take``.
    """
    turn = ledger.planning_turn
    return ledger.link_free(hop.connection, turn) and ledger.has_seat_from(
        hop.zone, ledger.arrival_turn(hop.zone)
    )


# --- zones ------------------------------------------------------------


def test_room_then_full(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L01: a free hop has room; once recorded, zone and link are used."""
    network = make_network("s-a a-g")
    ledger = TurnLedger(place(network, 2))
    into_a = hop(network, "s", "a")

    assert has_room(ledger, into_a) is True
    ledger.record("s", into_a)
    assert has_room(ledger, into_a) is False


def test_zone_capacity_boundary(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L02: a zone takes drones up to its limit; the link is not the cause."""
    network = make_network("s-a a-g", capacity={"a": 2}, links={"s-a": 3})
    ledger = TurnLedger(place(network, 3, at={1: "a"}))
    into_a = hop(network, "s", "a")

    assert has_room(ledger, into_a) is True
    ledger.record("s", into_a)
    assert has_room(ledger, into_a) is False


def test_recorded_departure_frees_room(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L03: a drone ordered out of a zone frees its room this turn."""
    network = make_network("s-a a-g")
    ledger = TurnLedger(place(network, 2, at={1: "a"}))

    ledger.record("a", hop(network, "a", "g"))

    assert has_room(ledger, hop(network, "s", "a")) is True


def test_unrecorded_departure_is_not_counted(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L04: only the orders recorded so far count (conservative)."""
    network = make_network("s-a a-g")
    ledger = TurnLedger(place(network, 2, at={1: "a"}))

    assert has_room(ledger, hop(network, "s", "a")) is False


def test_end_zone_has_no_limit(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L05: any number of drones may enter the end zone."""
    network = make_network("s-a a-g", capacity={"a": 5}, links={"a-g": 5})
    ledger = TurnLedger(
        place(network, 5, at={1: "a", 2: "a", 3: "a", 4: "a"})
    )
    into_g = hop(network, "a", "g")

    for _ in range(4):
        assert has_room(ledger, into_g) is True
        ledger.record("a", into_g)


def test_start_zone_has_no_limit(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L06: the start zone, still holding a drone, accepts one more."""
    network = make_network("s-a a-g", capacity={"a": 5}, links={"a-g": 5})
    ledger = TurnLedger(
        place(network, 5, at={1: "a", 2: "a", 3: "a", 4: "a"})
    )

    assert has_room(ledger, hop(network, "a", "s")) is True


# --- restricted zones and drones in flight ----------------------------


def test_reservation_fills_restricted_zone(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L07: a drone in flight toward r already takes r's only place."""
    network = make_network(
        "s-r s-q q-r r-g", types={"r": R}, links={"s-r": 2}
    )
    ledger = TurnLedger(
        place(network, 2, at={2: "q"}, flying={1: ("s", "r")})
    )

    assert has_room(ledger, hop(network, "q", "r")) is False


def test_landing_drone_frees_its_link(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L08: the landing D1 does not use link s-r, so D2 may depart."""
    network = make_network("s-r r-g", types={"r": R}, capacity={"r": 2})
    ledger = TurnLedger(place(network, 2, flying={1: ("s", "r")}))

    assert has_room(ledger, hop(network, "s", "r")) is True


def test_link_counts_only_departures(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L09: link use is the recorded departures; the landing is not one."""
    network = make_network(
        "s-r r-g", types={"r": R}, capacity={"r": 4}, links={"s-r": 2}
    )
    ledger = TurnLedger(place(network, 4, flying={1: ("s", "r")}))
    into_r = hop(network, "s", "r")

    assert has_room(ledger, into_r) is True
    ledger.record("s", into_r)
    assert has_room(ledger, into_r) is True
    ledger.record("s", into_r)
    # r still has a place left on turn 2, so the link is what is full.
    assert has_room(ledger, into_r) is False
    assert ledger.link_free(into_r.connection, 1) is False
    assert ledger.has_seat_from(network.get_zone("r"), 2) is True
    assert ledger.projected_load("r", 2) == 3


# --- connections ------------------------------------------------------


def test_link_is_shared_by_both_directions(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L10: a link used a->b cannot also be used b->a in the same turn."""
    network = make_network("s-a a-b b-g", capacity={"a": 2, "b": 2})
    ledger = TurnLedger(place(network, 2, at={1: "a", 2: "b"}))

    ledger.record("a", hop(network, "a", "b"))

    assert has_room(ledger, hop(network, "b", "a")) is False


def test_counts_are_kept_per_link_and_zone(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L11: a record only affects its own link and zones."""
    network = make_network("s-a s-b a-g b-g")
    ledger = TurnLedger(place(network, 3))

    ledger.record("s", hop(network, "s", "a"))

    assert has_room(ledger, hop(network, "s", "b")) is True
    assert has_room(ledger, hop(network, "s", "a")) is False


def test_ledger_does_not_change_state(
    make_network: MakeNetwork,
    place: Place,
    hop: MakeHop,
    snapshot: Snapshot,
) -> None:
    """L12: asking and recording never touch the simulation state."""
    network = make_network("s-a a-g")
    state = place(network, 2, at={1: "a"})
    before = snapshot(state)
    ledger = TurnLedger(state)

    has_room(ledger, hop(network, "a", "g"))
    ledger.record("a", hop(network, "a", "g"))
    has_room(ledger, hop(network, "s", "a"))
    ledger.record("s", hop(network, "s", "a"))

    assert snapshot(state) == before


# --- planned moves and later turns (timed reservation) ----------------


def ledger_with(state: SimulationState, *moves: Rv) -> TurnLedger:
    """Return a ledger over a table prepared for the turn, plus moves."""
    table = ReservationTable()
    table.start_turn(state)
    for move in moves:
        table.reserve(move)
    return TurnLedger(state, table)


def link(network: Network, name: str) -> Connection:
    """Return the connection written as ``name`` (``"a-b"``)."""
    zone_a, zone_b = name.split("-")
    connection = network.connection_between(zone_a, zone_b)
    assert connection is not None, f"no {name} link"
    return connection


def test_link_free_counts_this_turn_only_for_records(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L13: an order recorded this turn uses the link this turn only."""
    network = make_network("s-a a-g", capacity={"a": 2})
    ledger = TurnLedger(place(network, 2))

    ledger.record("s", hop(network, "s", "a"))

    assert ledger.link_free(link(network, "s-a"), 1) is False
    assert ledger.link_free(link(network, "s-a"), 2) is True


@pytest.mark.parametrize(
    ("edges", "at", "flying", "moves", "expected"),
    [
        pytest.param(
            "s-a a-g",
            {1: "a"},
            {},
            [Rv(1, "a", "g", 3, 3)],
            {("a-g", 2): True, ("a-g", 3): False, ("a-g", 4): True},
            id="departure-turn-only",
        ),
        pytest.param(
            "s-a a-b b-g",
            {1: "b", 2: "a"},
            {},
            [Rv(1, "b", "a", 2, 2)],
            {("a-b", 2): False},
            id="against-declared-order",
        ),
        pytest.param(
            "s-r r-g",
            {},
            {1: ("s", "r")},
            [],
            {("s-r", 1): True},
            id="landing-not-counted",
        ),
    ],
)
def test_link_free_counts_planned_departures(
    make_network: MakeNetwork,
    place: Place,
    edges: str,
    at: dict[int, str],
    flying: dict[int, tuple[str, str]],
    moves: list[Rv],
    expected: dict[tuple[str, int], bool],
) -> None:
    """L14: a planned move uses its link on its departure turn, both ways."""
    network = make_network(edges, types={"r": R})
    ledger = ledger_with(place(network, 2, at=at, flying=flying), *moves)

    for (name, turn), free in expected.items():
        assert ledger.link_free(link(network, name), turn) is free


def test_fits_with_extra(make_network: MakeNetwork, place: Place) -> None:
    """L15: ``extra`` drones fit up to the limit; start and end never fill."""
    network = make_network("s-a a-g", capacity={"a": 2})
    ledger = TurnLedger(place(network, 3, at={1: "a"}))
    zone = network.get_zone

    assert ledger.fits(zone("a"), 1, 1) is True
    assert ledger.fits(zone("a"), 1, 2) is False
    assert ledger.fits(zone("s"), 1, 100) is True
    assert ledger.fits(zone("g"), 1, 100) is True


def test_projected_load_accumulates(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L16: drones staying, plus entries, minus departures, turn by turn."""
    network = make_network("s-a a-g", capacity={"a": 2})
    ledger = ledger_with(
        place(network, 3, at={1: "a"}), Rv(1, "a", "g", 3, 3)
    )

    assert [ledger.projected_load("a", t) for t in range(1, 5)] == [1, 1, 0, 0]
    ledger.record("s", hop(network, "s", "a"))
    assert [ledger.projected_load("a", t) for t in range(1, 5)] == [2, 2, 1, 1]
    assert ledger.projected_load("s", 1) == 1


def test_restricted_record_counts_on_landing_turn(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L17: an order into r counts in r from the next turn on."""
    network = make_network(
        "s-r r-g", types={"r": R}, capacity={"r": 2}, links={"s-r": 2}
    )
    ledger = TurnLedger(place(network, 2))
    into_r = hop(network, "s", "r")

    ledger.record("s", into_r)

    assert ledger.projected_load("r", 1) == 0
    assert ledger.projected_load("r", 2) == 1
    assert has_room(ledger, into_r) is True


def test_seat_kept_for_later_is_not_taken(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L18: a has a seat now, but D2 is planned to enter it on turn 3."""
    network = make_network("s-a a-g b-a")
    ledger = ledger_with(
        place(network, 2, at={2: "b"}), Rv(2, "b", "a", 3, 3)
    )
    zone_a = network.get_zone("a")

    assert ledger.fits(zone_a, 1, 1) is True
    assert ledger.has_seat_from(zone_a, 1) is False
    assert has_room(ledger, hop(network, "s", "a")) is False
    assert ledger.horizon() == 3


@pytest.mark.parametrize("case", ["horizon", "arrival", "restricted-end"])
def test_horizon_and_arrival_turn(
    make_network: MakeNetwork, place: Place, case: str
) -> None:
    """L19: horizon is at least the next turn; restricted takes one more."""
    if case == "horizon":
        network = make_network("s-a a-g")
        state = place(network, 1)
        assert TurnLedger(state).horizon() == 2
        state.turn_number = 4
        ledger = TurnLedger(state)
        assert ledger.planning_turn == 5
        assert ledger.horizon() == 6
        assert ledger_with(state, Rv(1, "s", "a", 7, 8)).horizon() == 8
    elif case == "arrival":
        network = make_network("s-r s-a r-g a-g", types={"r": R})
        state = place(network, 1)
        state.turn_number = 3
        ledger = TurnLedger(state)
        assert ledger.arrival_turn(network.get_zone("r")) == 5
        assert ledger.arrival_turn(network.get_zone("a")) == 4
        assert ledger.arrival_turn(network.get_zone("g")) == 4
    else:
        network = make_network("s-g", types={"g": R})
        ledger = TurnLedger(place(network, 1))
        assert ledger.arrival_turn(network.get_zone("g")) == 2


@pytest.mark.parametrize("restricted", [False, True])
def test_cancel_undoes_record(
    make_network: MakeNetwork, place: Place, hop: MakeHop, restricted: bool
) -> None:
    """L20: cancel takes back the zone and link counts of a record."""
    name = "r" if restricted else "a"
    network = make_network(f"s-{name} {name}-g", types={"r": R})
    ledger = TurnLedger(place(network, 2))
    into = hop(network, "s", name)
    entered = 2 if restricted else 1

    ledger.record("s", into)
    assert ledger.projected_load(name, entered) == 1
    ledger.cancel("s", into)

    assert ledger.projected_load(name, entered) == 0
    assert has_room(ledger, into) is True
    assert ledger.link_free(into.connection, 1) is True


def test_ledger_without_table_loads_landings(
    make_network: MakeNetwork, place: Place
) -> None:
    """L21: without a table, the ledger makes one with the landings only:
    D1 landing in r counts there from turn 1, and nothing else is planned
    (the horizon is the default, the next turn)."""
    network = make_network("s-r r-g", types={"r": R})
    ledger = TurnLedger(place(network, 2, flying={1: ("s", "r")}))

    assert [ledger.projected_load("r", t) for t in (1, 2, 3)] == [1, 1, 1]
    assert ledger.projected_load("s", 1) == 1
    assert ledger.horizon() == 2
