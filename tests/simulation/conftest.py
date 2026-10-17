"""Fixtures for the simulation tests.

The engine tests (Stage 4) drive the loop with small stub schedulers.
They subclass ``Scheduler`` (a concrete class, not a Protocol) and are
handed out through factory fixtures, so the test files never import this
module directly. The subject's sample map and its expected output are
shared the same way, by the engine tests and the Stage 5 end-to-end tests.
"""

from typing import Callable

import pytest

from droneflow.models.drone import DroneStatus
from droneflow.models.network import Network
from droneflow.output.formatter import TurnLogFormatter
from droneflow.pathfinding.pathfinder import Hop, Pathfinder
from droneflow.simulation.scheduler import Scheduler
from droneflow.simulation.state import Move, MoveOrder, SimulationState
from droneflow.visualization.base import Visualizer

Script = list[list[MoveOrder]]
Record = tuple[int, int, bool]
Snapshot = dict[str, object]

SUBJECT_SAMPLE_MAP = """\
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
hub: tunnelB 7 4 [zone=normal color=red]
hub: obstacleX 5 5 [zone=blocked color=gray]
connection: hub-roof1
connection: hub-corridorA
connection: roof1-roof2
connection: roof2-goal
connection: corridorA-tunnelB [max_link_capacity=2]
connection: tunnelB-goal
"""

# The same map with corridorA blocked, so roof1 is the only way through.
RESTRICTED_ONLY_MAP = SUBJECT_SAMPLE_MAP.replace(
    "zone=priority color=green max_drones=2", "zone=blocked color=green"
)

SAMPLE_OUTPUT = [
    "D1-corridorA",
    "D1-tunnelB D2-corridorA",
    "D1-goal D2-tunnelB D3-corridorA",
    "D2-goal D3-tunnelB D4-corridorA",
    "D3-goal D4-tunnelB D5-corridorA",
    "D4-goal D5-tunnelB",
    "D5-goal",
]


class ScriptedScheduler(Scheduler):
    """Return the i-th list of a fixed script on turn i, then nothing."""

    def __init__(self, network: Network, script: Script) -> None:
        super().__init__(network, Pathfinder(network))
        self.script = script

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Return this turn's orders from the script."""
        turn = state.turn_number
        return list(self.script[turn]) if turn < len(self.script) else []


class IdleScheduler(Scheduler):
    """Never order anything."""

    def __init__(self, network: Network) -> None:
        super().__init__(network, Pathfinder(network))

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Return no orders."""
        return []


class OscillatingScheduler(Scheduler):
    """Move D1 back and forth between two zones forever."""

    def __init__(self, network: Network, zone_a: str, zone_b: str) -> None:
        super().__init__(network, Pathfinder(network))
        self.zone_a = zone_a
        self.zone_b = zone_b

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Send D1 to whichever of the two zones it is not in."""
        here = state.drones[1].current_zone
        target = self.zone_b if here == self.zone_a else self.zone_a
        return [MoveOrder(1, target)]


class FollowerScheduler(Scheduler):
    """Greedy test scheduler: each drone takes its first free shortest hop.

    Drones are considered in drone_id order (drones in flight are skipped).
    A hop is free when the zone still has room, counting departures and
    entries already decided this turn, and the connection still has room,
    counting drones landing over it. No optimization: just enough to run
    small maps to completion deterministically.
    """

    def __init__(self, network: Network) -> None:
        super().__init__(network, Pathfinder(network))

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
                free = state.free_capacity(name)
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

    def render(self, state: SimulationState) -> None:
        """Append a summary of the state."""
        self.records.append(
            (state.turn_number, state.delivered_count, state.is_complete)
        )


def place_drones(
    network: Network,
    nb_drones: int,
    at: dict[int, str] | None = None,
    flying: dict[int, tuple[str, str]] | None = None,
) -> SimulationState:
    """Return a state with some drones moved away from the start zone.

    ``at={1: "a"}`` puts D1 in zone a (the end zone delivers it) and
    ``flying={1: ("s", "r")}`` puts D1 in flight from s toward r. The
    unchecked primitives are used, so the zones need not be adjacent to
    the start; drones not listed stay in the start zone.
    """
    state = SimulationState(network, nb_drones)
    for drone_id, zone in (at or {}).items():
        state.enter_zone(drone_id, zone)
    for drone_id, (from_zone, to_zone) in (flying or {}).items():
        connection = network.connection_between(from_zone, to_zone)
        assert connection is not None, f"no {from_zone}-{to_zone} link"
        state.enter_transit(drone_id, connection, to_zone)
    return state


def make_hop(network: Network, from_zone: str, to_zone: str) -> Hop:
    """Return the hop from one zone into an adjacent one, in any direction.

    Unlike ``Pathfinder.next_hops`` it also builds hops that are not
    shortest moves (back to the start, for instance).
    """
    connection = network.connection_between(from_zone, to_zone)
    assert connection is not None, f"no {from_zone}-{to_zone} link"
    return Hop(connection, network.get_zone(to_zone))


def make_real_scheduler(network: Network) -> Scheduler:
    """Return the Stage 5 scheduler over its own pathfinder."""
    return Scheduler(network, Pathfinder(network))


def take_snapshot(state: SimulationState) -> Snapshot:
    """Copy every value a turn may change, for before/after comparison."""
    network = state.network
    return {
        "turn": state.turn_number,
        "drones": {
            drone_id: (
                d.current_zone,
                d.status,
                d.in_transit_connection,
                d.transit_target,
                d.turns_remaining,
            )
            for drone_id, d in state.drones.items()
        },
        "zones": {
            name: (state.occupancy(name), state.reserved(name))
            for name in network.zones
        },
        "links": {c.name: state.link_load(c) for c in network.connections},
    }


@pytest.fixture
def scripted_scheduler() -> Callable[[Network, Script], Scheduler]:
    """Return a factory for ``ScriptedScheduler``."""
    return ScriptedScheduler


@pytest.fixture
def idle_scheduler() -> Callable[[Network], Scheduler]:
    """Return a factory for ``IdleScheduler``."""
    return IdleScheduler


@pytest.fixture
def oscillating_scheduler() -> Callable[[Network, str, str], Scheduler]:
    """Return a factory for ``OscillatingScheduler``."""
    return OscillatingScheduler


@pytest.fixture
def follower_scheduler() -> Callable[[Network], Scheduler]:
    """Return a factory for ``FollowerScheduler``."""
    return FollowerScheduler


@pytest.fixture
def place() -> Callable[..., SimulationState]:
    """Return the ``place_drones`` helper."""
    return place_drones


@pytest.fixture
def hop() -> Callable[[Network, str, str], Hop]:
    """Return the ``make_hop`` helper."""
    return make_hop


@pytest.fixture
def real_scheduler() -> Callable[[Network], Scheduler]:
    """Return a factory for the real ``Scheduler`` (Stage 5)."""
    return make_real_scheduler


@pytest.fixture
def recorder() -> tuple[Visualizer, list[Record]]:
    """Return a recording visualizer and the list it appends to."""
    visualizer = RecordingVisualizer()
    return visualizer, visualizer.records


@pytest.fixture
def snapshot() -> Callable[[SimulationState], Snapshot]:
    """Return the ``take_snapshot`` helper."""
    return take_snapshot


@pytest.fixture
def fmt() -> Callable[[list[Move]], str]:
    """Return a function formatting one turn as it would be printed."""
    return TurnLogFormatter().format_turn


@pytest.fixture
def subject_map() -> str:
    """Return the subject's sample map (the one before chapter VII.5)."""
    return SUBJECT_SAMPLE_MAP


@pytest.fixture
def subject_output() -> list[str]:
    """Return the expected seven output lines of the sample map."""
    return list(SAMPLE_OUTPUT)


@pytest.fixture
def restricted_only_map() -> str:
    """Return the sample map with corridorA blocked (roof1 only)."""
    return RESTRICTED_ONLY_MAP
