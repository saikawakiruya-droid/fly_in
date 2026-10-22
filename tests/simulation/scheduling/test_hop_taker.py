"""Tests for droneflow.simulation.scheduling.hop_taker (HopTaker).

``taker_for(state, table=None)`` builds the table, the ledger, the board
and the taker for the state's next turn (moves reserved in ``table``
beforehand are kept). The hops tried are ``Pathfinder.next_hops``. The
taker tries every hop without evicting first, then again in the same
order letting the ``Evictor`` make room: into a restricted zone the zone
needs one more seat from the landing turn (``extra=1``); into another
zone that has a seat now but not on a later turn the drone enters first,
then the zone needs no extra seat from the next turn on (``extra=0``),
and a failure undoes the move.
"""

from typing import Callable

from droneflow.models.connection import Connection
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.pathfinding.pathfinder import Hop, Pathfinder
from droneflow.simulation.scheduling.hop_taker import HopTaker
from droneflow.simulation.scheduling.positions import PositionBoard
from droneflow.simulation.scheduling.reservation_table import (
    Reservation,
    ReservationTable,
)
from droneflow.simulation.state import SimulationState
from droneflow.simulation.scheduling.turn_ledger import TurnLedger

MakeNetwork = Callable[..., Network]
Place = Callable[..., SimulationState]
TakerFor = Callable[
    ..., tuple[ReservationTable, TurnLedger, PositionBoard, HopTaker]
]
MovesOf = Callable[[ReservationTable, int], list[Reservation]]
Rv = Reservation

R = ZoneType.RESTRICTED


def hops_from(network: Network, here: str) -> list[Hop]:
    """Return the shortest next hops of ``here``."""
    return Pathfinder(network).next_hops(here)


def link(network: Network, a: str, b: str) -> Connection:
    """Return the connection between two zones."""
    connection = network.connection_between(a, b)
    assert connection is not None
    return connection


def test_free_hop_is_recorded_in_ledger_and_board(
    make_network: MakeNetwork,
    place: Place,
    taker_for: TakerFor,
    moves_of: MovesOf,
) -> None:
    """HT01: a free hop goes into the ledger and the board; once the link
    and the zone are full the next drone gets None and stays put."""
    network = make_network("s-a a-g")
    table, ledger, board, taker = taker_for(place(network, 2))
    hops = hops_from(network, "s")

    taken = taker.take_first(1, "s", hops)

    assert taken is not None
    assert taken.zone.name == "a"
    assert board.where(1) == ("a", 1)
    assert ledger.projected_load("a", 1) == 1
    assert ledger.link_free(link(network, "s", "a"), 1) is False
    assert moves_of(table, 1) == []

    assert taker.take_first(2, "s", hops) is None
    assert board.where(2) == ("s", 0)


def test_land_in_restricted_zone_after_evicting(
    make_network: MakeNetwork,
    place: Place,
    taker_for: TakerFor,
    moves_of: MovesOf,
) -> None:
    """HT02: into a full restricted zone, its occupant is evicted so that
    the zone has a seat from the landing turn on (``extra=1``)."""
    network = make_network("s-r r-g", types={"r": R})
    table, _, board, taker = taker_for(place(network, 2, at={1: "r"}))

    taken = taker.take_first(2, "s", hops_from(network, "s"))

    assert taken is not None
    assert taken.zone.name == "r"
    assert board.where(2) == ("r", 2)
    assert moves_of(table, 1) == [Rv(1, "r", "g", 2, 2)]
    assert moves_of(table, 2) == []


def test_evictions_chain(
    make_network: MakeNetwork,
    place: Place,
    taker_for: TakerFor,
    moves_of: MovesOf,
) -> None:
    """HT03: the evictor goes down the chain (D1 out of r needs D2 out of
    x) before the drone lands."""
    network = make_network("s-r r-x x-g", types={"r": R})
    table, _, board, taker = taker_for(place(network, 3, at={1: "r", 2: "x"}))

    taken = taker.take_first(3, "s", hops_from(network, "s"))

    assert taken is not None
    assert taken.zone.name == "r"
    assert board.where(3) == ("r", 2)
    assert moves_of(table, 1) == [Rv(1, "r", "x", 2, 2)]
    assert moves_of(table, 2) == [Rv(2, "x", "g", 2, 2)]


def test_failed_eviction_changes_nothing(
    make_network: MakeNetwork,
    place: Place,
    taker_for: TakerFor,
    moves_of: MovesOf,
) -> None:
    """HT04: D1 already leaves r on turn 3, too late: None, and the ledger,
    the board and the table are as they were."""
    network = make_network("s-r r-g", types={"r": R})
    table = ReservationTable()
    table.reserve(Rv(1, "r", "g", 3, 3))
    table, ledger, board, taker = taker_for(
        place(network, 2, at={1: "r"}), table
    )

    assert taker.take_first(2, "s", hops_from(network, "s")) is None
    assert board.where(2) == ("s", 0)
    assert moves_of(table, 1) == [Rv(1, "r", "g", 3, 3)]
    assert ledger.link_free(link(network, "s", "r"), 1) is True


def test_enter_then_evict(
    make_network: MakeNetwork,
    place: Place,
    taker_for: TakerFor,
    moves_of: MovesOf,
) -> None:
    """HT05: a is free now but kept for D2 on turn 2; D1 enters, then is
    evicted itself so that a fits on turn 2 (``extra=0``)."""
    network = make_network("s-a a-g")
    table = ReservationTable()
    table.reserve(Rv(2, "s", "a", 2, 2))
    table, ledger, board, taker = taker_for(place(network, 2), table)
    zone_a = network.get_zone("a")
    assert ledger.has_seat_from(zone_a, 1) is False
    assert ledger.fits(zone_a, 1, 1) is True

    taken = taker.take_first(1, "s", hops_from(network, "s"))

    assert taken is not None
    assert taken.zone.name == "a"
    assert board.where(1) == ("a", 1)
    assert moves_of(table, 1) == [Rv(1, "a", "g", 2, 2)]
    assert moves_of(table, 2) == [Rv(2, "s", "a", 2, 2)]
    assert ledger.projected_load("a", 1) == 1
    assert ledger.projected_load("a", 2) == 1


def test_enter_then_evict_is_undone_on_failure(
    make_network: MakeNetwork,
    place: Place,
    taker_for: TakerFor,
    moves_of: MovesOf,
) -> None:
    """HT06: D1 could enter a, but cannot be evicted (D5 takes a-g on turn
    2): the record is cancelled, D1 is back in s and the table is as it
    was."""
    network = make_network("s-a a-g", capacity={"a": 2})
    table = ReservationTable()
    table.reserve(Rv(5, "a", "g", 2, 2))
    table.reserve(Rv(2, "s", "a", 2, 2))
    table.reserve(Rv(6, "s", "a", 2, 2))
    table, ledger, board, taker = taker_for(
        place(network, 6, at={5: "a"}), table
    )
    mark = table.mark()

    assert taker.take_first(1, "s", hops_from(network, "s")) is None
    assert board.where(1) == ("s", 0)
    assert board.drones_in("a") == [5]
    assert ledger.projected_load("a", 1) == 1
    assert ledger.link_free(link(network, "s", "a"), 1) is True
    assert table.mark() == mark
    assert moves_of(table, 1) == []


def test_every_hop_without_eviction_comes_first(
    make_network: MakeNetwork,
    place: Place,
    taker_for: TakerFor,
    moves_of: MovesOf,
) -> None:
    """HT07: eviction is a last resort: the later hop is tried without
    evicting before the first hop is taken by evicting."""
    network = make_network("s-a a-g s-b b-g", types={"a": R, "b": R})
    hops = hops_from(network, "s")
    assert [hop.zone.name for hop in hops] == ["a", "b"]

    table, _, board, taker = taker_for(place(network, 3, at={1: "a"}))
    taken = taker.take_first(2, "s", hops)
    assert taken is not None
    assert taken.zone.name == "b"
    assert board.where(2) == ("b", 2)
    assert moves_of(table, 1) == []

    table, _, board, taker = taker_for(
        place(network, 3, at={1: "a", 3: "b"})
    )
    taken = taker.take_first(2, "s", hops)
    assert taken is not None
    assert taken.zone.name == "a"
    assert moves_of(table, 1) == [Rv(1, "a", "g", 2, 2)]
    assert moves_of(table, 3) == []


def test_no_hop(
    make_network: MakeNetwork, place: Place, taker_for: TakerFor
) -> None:
    """HT08: with no hop to try the answer is None."""
    network = make_network("s-a a-g")
    _, _, _, taker = taker_for(place(network, 2))

    assert taker.take_first(2, "s", []) is None
