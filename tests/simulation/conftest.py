"""Fixtures for the simulation tests.

The engine tests (Stage 4) drive the loop with small stub schedulers.
They are plain classes with ``decide_moves`` (they satisfy
``MoveDecider``), handed to ``SimulationEngine`` directly, and are handed
out through factory fixtures, so the test files never import this
module directly. The subject's sample map and its expected output are
shared the same way; they live in ``tests/conftest.py`` with ``place`` and
``snapshot``, since the visualization tests use them too.

``evictor_for`` builds a ``ReservationTable``, a ``TurnLedger`` and an
``Evictor`` for one turn, for the timed reservation tests. ``moves_of``
lists a drone's planned moves from the table's public ``due`` and
``last_turn``.
"""

from typing import Callable

import pytest

from droneflow.models.drone import DroneStatus
from droneflow.models.network import Network
from droneflow.output.formatter import TurnLogFormatter
from droneflow.pathfinding.pathfinder import Hop, Pathfinder
from droneflow.simulation.engine import MoveDecider
from droneflow.simulation.evictor import Evictor
from droneflow.simulation.observer import TurnObserver
from droneflow.simulation.positions import PositionBoard
from droneflow.simulation.reservation_table import (
    Reservation,
    ReservationTable,
)
from droneflow.simulation.scheduler import Scheduler
from droneflow.simulation.state import Move, MoveOrder, SimulationState
from droneflow.simulation.turn_ledger import TurnLedger

Script = list[list[MoveOrder]]
Record = tuple[int, int, bool]
Call = tuple[object, ...]
EvictorParts = tuple[ReservationTable, TurnLedger, Evictor]


class ScriptedScheduler:
    """Return the i-th list of a fixed script on turn i, then nothing."""

    def __init__(self, script: Script) -> None:
        """Keep the script."""
        self.script = script

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Return this turn's orders from the script."""
        turn = state.turn_number
        return list(self.script[turn]) if turn < len(self.script) else []


class IdleScheduler:
    """Never order anything."""

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Return no orders."""
        return []


class OscillatingScheduler:
    """Move D1 back and forth between two zones forever."""

    def __init__(self, zone_a: str, zone_b: str) -> None:
        """Keep the two zones."""
        self.zone_a = zone_a
        self.zone_b = zone_b

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Send D1 to whichever of the two zones it is not in."""
        here = state.drones[1].current_zone
        target = self.zone_b if here == self.zone_a else self.zone_a
        return [MoveOrder(1, target)]


class FollowerScheduler:
    """Greedy test scheduler: each drone takes its first free shortest hop.

    Drones are considered in drone_id order (drones in flight are skipped).
    A hop is free when the zone still has room, counting departures and
    entries already decided this turn, and the connection still has room,
    counting drones landing over it. No optimization: just enough to run
    small maps to completion deterministically.
    """

    def __init__(self, network: Network) -> None:
        """Build a pathfinder over the network."""
        self.network = network
        self.pathfinder = Pathfinder(network)

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Return one order per drone that can move along a shortest path."""
        zone_change: dict[str, int] = {}
        link_used: dict[str, int] = {
            c.name: state.link_load(c) for c in self.network.connections
        }
        orders: list[MoveOrder] = []
        for drone in state.active_drones():
            here = drone.current_zone
            if drone.status is not DroneStatus.AT_ZONE or here is None:
                continue
            for hop in self.pathfinder.next_hops(here):
                name = hop.zone.name
                capacity = hop.zone.capacity
                free = (
                    None if capacity is None
                    else capacity - state.load(name)
                )
                if free is not None and free + zone_change.get(name, 0) < 1:
                    continue
                link = hop.connection
                if link_used[link.name] >= link.max_link_capacity:
                    continue
                link_used[link.name] += 1
                zone_change[name] = zone_change.get(name, 0) - 1
                zone_change[here] = zone_change.get(here, 0) + 1
                orders.append(MoveOrder(drone.drone_id, name))
                break
        return orders


class RecordingVisualizer:
    """Record ``(turn_number, delivered_count, is_complete)`` per render."""

    def __init__(self) -> None:
        self.records: list[Record] = []

    def begin(self, state: SimulationState) -> None:
        """Record nothing: only renders after a turn are recorded."""

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Append a summary of the state."""
        self.records.append(
            (state.turn_number, state.delivered_count, state.is_complete)
        )

    def close(self) -> None:
        """Record nothing."""


class CallLogVisualizer:
    """Log every call, in order, in one list (Stage 7 hook tests).

    Entries are ``("begin", turn, drones in the start zone)``,
    ``("render", turn, moves)`` and ``("close",)``. Values are copied
    when the call is made, since the engine keeps changing the state.
    ``fail_on`` names a method that raises ``RuntimeError("view")``
    after logging its call.
    """

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[Call] = []
        self.fail_on = fail_on

    def begin(self, state: SimulationState) -> None:
        """Log the turn and how many drones wait in the start zone."""
        start = state.network.start_zone.name
        self._log("begin", state.turn_number, state.occupancy(start))

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Log the turn and a copy of its moves."""
        self._log("render", state.turn_number, list(moves))

    def close(self) -> None:
        """Log the call."""
        self._log("close")

    def _log(self, name: str, *values: object) -> None:
        self.calls.append((name, *values))
        if self.fail_on == name:
            raise RuntimeError("view")


def make_hop(network: Network, from_zone: str, to_zone: str) -> Hop:
    """Return the hop from one zone into an adjacent one, in any direction.

    Unlike ``Pathfinder.next_hops`` it also builds hops that are not
    shortest moves (back to the start, for instance).
    """
    connection = network.connection_between(from_zone, to_zone)
    assert connection is not None, f"no {from_zone}-{to_zone} link"
    return Hop(connection, network.get_zone(to_zone))


def table_moves_of(
    table: ReservationTable, drone_id: int
) -> list[Reservation]:
    """Return the drone's planned moves, earliest departure first.

    Built from the public ``due`` and ``last_turn``: every move departs
    on or before the turn it arrives, which is at most ``last_turn``.
    """
    return [
        move for turn in range(table.last_turn() + 1)
        for move in table.due(turn) if move.drone_id == drone_id
    ]


def make_real_scheduler(network: Network) -> Scheduler:
    """Return the Stage 5 scheduler over its own pathfinder."""
    return Scheduler(network, Pathfinder(network))


def make_evictor(
    state: SimulationState, table: ReservationTable | None = None
) -> EvictorParts:
    """Return a table, a ledger and an evictor for the state's next turn.

    Without ``table`` a new one is made. The table is prepared with
    ``start_turn`` before the ledger is built over it. The board comes from
    ``PositionBoard.from_state``, as in the scheduler: a drone landing
    this turn is in its target zone from this turn on, a drone standing in
    a zone has been there since the turn just played, and delivered drones
    are left out.
    """
    network = state.network
    if table is None:
        table = ReservationTable()
    table.start_turn(state)
    ledger = TurnLedger(state, table)
    pathfinder = Pathfinder(network)
    hops = {name: pathfinder.next_hops(name) for name in network.zones}
    board = PositionBoard.from_state(state)
    return table, ledger, Evictor(ledger, table, hops, board)


@pytest.fixture
def scripted_scheduler() -> Callable[[Network, Script], MoveDecider]:
    """Return a factory for ``ScriptedScheduler`` (the network is unused)."""
    return lambda network, script: ScriptedScheduler(script)


@pytest.fixture
def idle_scheduler() -> Callable[[Network], MoveDecider]:
    """Return a factory for ``IdleScheduler`` (the network is unused)."""
    return lambda network: IdleScheduler()


@pytest.fixture
def oscillating_scheduler() -> Callable[[Network, str, str], MoveDecider]:
    """Return a factory for ``OscillatingScheduler`` (network unused)."""
    return lambda network, a, b: OscillatingScheduler(a, b)


@pytest.fixture
def follower_scheduler() -> Callable[[Network], MoveDecider]:
    """Return a factory for ``FollowerScheduler``."""
    return FollowerScheduler


@pytest.fixture
def hop() -> Callable[[Network, str, str], Hop]:
    """Return the ``make_hop`` helper."""
    return make_hop


@pytest.fixture
def real_scheduler() -> Callable[[Network], Scheduler]:
    """Return a factory for the real ``Scheduler`` (Stage 5)."""
    return make_real_scheduler


@pytest.fixture
def moves_of() -> Callable[[ReservationTable, int], list[Reservation]]:
    """Return the ``table_moves_of`` helper."""
    return table_moves_of


@pytest.fixture
def evictor_for() -> Callable[..., EvictorParts]:
    """Return the ``make_evictor`` helper (timed reservation tests)."""
    return make_evictor


@pytest.fixture
def recorder() -> tuple[TurnObserver, list[Record]]:
    """Return a recording observer and the list it appends to."""
    visualizer = RecordingVisualizer()
    return visualizer, visualizer.records


@pytest.fixture
def fmt() -> Callable[[list[Move]], str]:
    """Return a function formatting one turn as it would be printed."""
    return TurnLogFormatter().format_turn


@pytest.fixture
def call_log() -> Callable[..., CallLogVisualizer]:
    """Return a factory for ``CallLogVisualizer`` (``fail_on`` optional)."""
    return CallLogVisualizer
