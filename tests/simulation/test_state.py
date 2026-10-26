"""Tests for droneflow.simulation.state (SimulationState)."""

from typing import Callable

import dataclasses

import pytest

from droneflow.errors import SimulationError
from droneflow.models.connection import Connection
from droneflow.models.drone import DroneStatus
from droneflow.models.network import Network
from droneflow.models.zone import ZoneType
from droneflow.simulation.state import Move, MoveOrder, SimulationState
from droneflow.simulation.turn_resolver import TurnResolver

MakeNetwork = Callable[..., Network]

R = ZoneType.RESTRICTED


def link(network: Network, zone_a: str, zone_b: str) -> Connection:
    """Return the connection between two zones, failing if there is none."""
    connection = network.connection_between(zone_a, zone_b)
    assert connection is not None
    return connection


def test_new_state_puts_every_drone_at_start(
    make_network: MakeNetwork,
) -> None:
    """S01: drones 1..n start AT_ZONE in the start zone."""
    state = SimulationState(make_network("s-a a-g"), 3)

    assert state.turn_number == 0
    assert list(state.drones) == [1, 2, 3]
    for drone in state.drones.values():
        assert drone.current_zone == "s"
        assert drone.status is DroneStatus.AT_ZONE
    assert state.occupancy("s") == 3
    assert [d.drone_id for d in state.active_drones()] == [1, 2, 3]
    assert state.delivered_count == 0
    assert state.is_complete is False


def test_enter_zone_moves_occupancy(make_network: MakeNetwork) -> None:
    """S03: enter_zone moves one drone's occupancy between zones."""
    state = SimulationState(make_network("s-a a-g"), 3)
    state.enter_zone(1, "a")

    assert state.occupancy("s") == 2
    assert state.occupancy("a") == 1


def test_entering_end_delivers(make_network: MakeNetwork) -> None:
    """S04: a drone entering the end zone is delivered and not counted."""
    state = SimulationState(make_network("s-g"), 2)
    state.enter_zone(1, "g")

    assert state.drones[1].status is DroneStatus.DELIVERED
    assert state.occupancy("g") == 0
    assert 1 not in [d.drone_id for d in state.active_drones()]
    assert state.delivered_count == 1
    assert state.is_complete is False

    state.enter_zone(2, "g")
    assert state.is_complete is True


def test_enter_transit_reserves_target(make_network: MakeNetwork) -> None:
    """S05: taking off reserves the target and occupies the connection."""
    network = make_network("s-r r-g", types={"r": R})
    state = SimulationState(network, 1)
    connection = link(network, "s", "r")
    state.enter_transit(1, connection, "r")

    drone = state.drones[1]
    assert drone.status is DroneStatus.IN_TRANSIT
    assert drone.current_zone is None
    assert drone.in_transit_connection == "s-r"
    assert drone.transit_target == "r"
    assert state.occupancy("r") == 0
    assert state.reserved("r") == 1
    assert state.load("r") == 1
    assert state.link_load(connection) == 1
    assert state.drones_in_transit() == [drone]


def test_complete_transit_turns_reservation_into_occupancy(
    make_network: MakeNetwork,
) -> None:
    """S06: landing replaces the reservation and frees the connection."""
    network = make_network("s-r r-g", types={"r": R})
    state = SimulationState(network, 1)
    connection = link(network, "s", "r")
    state.enter_transit(1, connection, "r")
    state.complete_transit(1)

    drone = state.drones[1]
    assert drone.status is DroneStatus.AT_ZONE
    assert drone.current_zone == "r"
    assert drone.in_transit_connection is None
    assert drone.transit_target is None
    assert state.reserved("r") == 0
    assert state.occupancy("r") == 1
    assert state.load("r") == 1
    assert state.link_load(connection) == 0


def test_landing_in_restricted_end_delivers(
    make_network: MakeNetwork,
) -> None:
    """S07: landing in a restricted end leaves no reservation behind."""
    network = make_network("s-g", types={"g": R})
    state = SimulationState(network, 1)
    state.enter_transit(1, link(network, "s", "g"), "g")
    state.complete_transit(1)

    assert state.drones[1].status is DroneStatus.DELIVERED
    assert state.reserved("g") == 0
    assert state.occupancy("g") == 0
    assert state.is_complete is True


def test_basic_operations_refuse_broken_preconditions(
    make_network: MakeNetwork,
) -> None:
    """S08: the unchecked operations still refuse impossible states."""
    network = make_network("s-r r-g", types={"r": R})
    state = SimulationState(network, 2)
    connection = link(network, "s", "r")
    state.enter_transit(1, connection, "r")

    with pytest.raises(SimulationError, match="not in a zone"):
        state.enter_zone(1, "g")
    with pytest.raises(SimulationError, match="not in a zone"):
        state.enter_transit(1, connection, "r")
    with pytest.raises(SimulationError, match="not in flight"):
        state.complete_transit(2)


# --- Move -------------------------------------------------------------


def test_move_text_and_default() -> None:
    """MV01: the printed text, and no connection name by default."""
    assert Move(3, "x").text == "D3-x"
    assert Move(12, "a-b", "a-b").text == "D12-a-b"
    assert Move(3, "x").connection_name is None


def test_resolver_sets_the_connection_name(
    make_network: MakeNetwork,
) -> None:
    """MV02: departures carry the connection used (a departure toward a
    restricted zone has it as destination too); a landing carries None."""
    network = make_network("s-a a-r r-g", types={"r": R})
    state = SimulationState(network, 2)
    resolver = TurnResolver(network)

    assert resolver.resolve(state, [MoveOrder(1, "a")]) == [
        Move(1, "a", "s-a")
    ]
    second = resolver.resolve(state, [MoveOrder(1, "r"), MoveOrder(2, "a")])
    assert second == [Move(1, "a-r", "a-r"), Move(2, "a", "s-a")]
    assert " ".join(move.text for move in second) == "D1-a-r D2-a"
    assert resolver.resolve(state, []) == [Move(1, "r", None)]
    assert resolver.resolve(state, [MoveOrder(1, "g")]) == [
        Move(1, "g", "r-g")
    ]


def test_move_is_frozen_and_compares_the_connection() -> None:
    """MV03: a Move cannot be changed, and the connection name is part of
    its equality."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(Move(1, "a"), "destination", "b")
    assert len({Move(1, "a"), Move(1, "a")}) == 1
    assert (Move(1, "a") == Move(1, "a", None)) is True
    assert (Move(1, "a") == Move(1, "a", "s-a")) is False
