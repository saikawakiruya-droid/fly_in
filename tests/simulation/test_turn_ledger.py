"""Tests for droneflow.simulation.turn_ledger (TurnLedger)."""

from typing import Callable

from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.pathfinding.pathfinder import Hop
from droneflow.simulation.state import SimulationState
from droneflow.simulation.turn_ledger import TurnLedger

MakeNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]
MakeHop = Callable[[Network, str, str], Hop]
Snapshot = Callable[[SimulationState], dict[str, object]]

R = ZoneType.RESTRICTED


# --- zones ------------------------------------------------------------


def test_room_then_full(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L01: a free hop has room; once recorded, zone and link are used."""
    network = make_network("s-a a-g")
    ledger = TurnLedger(place(network, 2))
    into_a = hop(network, "s", "a")

    assert ledger.has_room(into_a) is True
    ledger.record("s", into_a)
    assert ledger.has_room(into_a) is False


def test_zone_capacity_boundary(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L02: a zone takes drones up to its limit; the link is not the cause."""
    network = make_network("s-a a-g", capacity={"a": 2}, links={"s-a": 3})
    ledger = TurnLedger(place(network, 3, at={1: "a"}))
    into_a = hop(network, "s", "a")

    assert ledger.has_room(into_a) is True
    ledger.record("s", into_a)
    assert ledger.has_room(into_a) is False


def test_recorded_departure_frees_room(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L03: a drone ordered out of a zone frees its room this turn."""
    network = make_network("s-a a-g")
    ledger = TurnLedger(place(network, 2, at={1: "a"}))

    ledger.record("a", hop(network, "a", "g"))

    assert ledger.has_room(hop(network, "s", "a")) is True


def test_unrecorded_departure_is_not_counted(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L04: only the orders recorded so far count (conservative)."""
    network = make_network("s-a a-g")
    ledger = TurnLedger(place(network, 2, at={1: "a"}))

    assert ledger.has_room(hop(network, "s", "a")) is False


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
        assert ledger.has_room(into_g) is True
        ledger.record("a", into_g)


def test_start_zone_has_no_limit(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L06: the start zone, still holding a drone, accepts one more."""
    network = make_network("s-a a-g", capacity={"a": 5}, links={"a-g": 5})
    ledger = TurnLedger(
        place(network, 5, at={1: "a", 2: "a", 3: "a", 4: "a"})
    )

    assert ledger.has_room(hop(network, "a", "s")) is True


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

    assert ledger.has_room(hop(network, "q", "r")) is False


def test_drone_in_flight_uses_its_link(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L08: r has room, but the landing drone still uses link s-r."""
    network = make_network("s-r r-g", types={"r": R}, capacity={"r": 2})
    ledger = TurnLedger(place(network, 2, flying={1: ("s", "r")}))

    assert ledger.has_room(hop(network, "s", "r")) is False


def test_link_counts_flight_and_orders_together(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L09: link use is the landing drones plus the recorded orders."""
    network = make_network(
        "s-r r-g", types={"r": R}, capacity={"r": 3}, links={"s-r": 2}
    )
    ledger = TurnLedger(place(network, 3, flying={1: ("s", "r")}))
    into_r = hop(network, "s", "r")

    assert ledger.has_room(into_r) is True
    ledger.record("s", into_r)
    # r still has one place left, so the link is what is full.
    assert ledger.has_room(into_r) is False


# --- connections ------------------------------------------------------


def test_link_is_shared_by_both_directions(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L10: a link used a->b cannot also be used b->a in the same turn."""
    network = make_network("s-a a-b b-g", capacity={"a": 2, "b": 2})
    ledger = TurnLedger(place(network, 2, at={1: "a", 2: "b"}))

    ledger.record("a", hop(network, "a", "b"))

    assert ledger.has_room(hop(network, "b", "a")) is False


def test_counts_are_kept_per_link_and_zone(
    make_network: MakeNetwork, place: Place, hop: MakeHop
) -> None:
    """L11: a record only affects its own link and zones."""
    network = make_network("s-a s-b a-g b-g")
    ledger = TurnLedger(place(network, 3))

    ledger.record("s", hop(network, "s", "a"))

    assert ledger.has_room(hop(network, "s", "b")) is True
    assert ledger.has_room(hop(network, "s", "a")) is False


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

    ledger.has_room(hop(network, "a", "g"))
    ledger.record("a", hop(network, "a", "g"))
    ledger.has_room(hop(network, "s", "a"))
    ledger.record("s", hop(network, "s", "a"))

    assert snapshot(state) == before
