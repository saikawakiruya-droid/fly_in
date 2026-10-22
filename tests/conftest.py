"""Fixtures shared by every test package.

``make_network`` builds a small network in code, and ``write_map``
writes a map file for end-to-end tests that go through the parser
(``load_world`` parses it too). ``place`` and ``snapshot`` build and copy
simulation states, and the subject's sample map with its expected output
is shared by the simulation and the visualization tests: the subject's
seven-line example (``subject_output``) and the five lines the real
scheduler prints (``scheduler_output``). ``tty_stream``
makes a ``StringIO`` that claims to be a terminal, for the terminal view
(which only asks ``isatty()``) and the application tests.
``provided_map`` and ``maps_archive`` read the maps handed out with the
subject from ``maps.tar.gz`` at the repository root without extracting
it, for the end-to-end tests of the scheduler. ``stuck_after`` hands out
``StuckScheduler`` makers to pass as ``Application(make_scheduler=...)``,
for runs that stop part-way.
"""

import functools
import io
import tarfile
from pathlib import Path
from typing import Callable, Protocol

import pytest

from droneflow.models.connection import Connection
from droneflow.models.network import Network
from droneflow.models.world import World
from droneflow.models.zone import Zone, ZoneRole, ZoneType
from droneflow.parsing.map_parser import MapParser
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.engine import MoveDecider
from droneflow.simulation.scheduling.scheduler import Scheduler
from droneflow.simulation.state import MoveOrder, SimulationState

Snapshot = dict[str, object]

MAPS_ARCHIVE = Path(__file__).resolve().parents[1] / "maps.tar.gz"

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

# What the real scheduler prints for the sample map: two drones go round
# by roof1, so it takes five turns instead of the subject's seven.
SCHEDULER_OUTPUT = [
    "D1-corridorA D2-hub-roof1",
    "D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1",
    "D1-goal D2-roof2 D3-tunnelB D4-roof1 D5-corridorA",
    "D2-goal D3-goal D4-roof2 D5-tunnelB",
    "D4-goal D5-goal",
]


class StuckScheduler:
    """The real scheduler for ``ok_turns`` turns, then nothing at all."""

    def __init__(
        self, network: Network, pathfinder: Pathfinder, ok_turns: int
    ) -> None:
        """Wrap a real scheduler over the same network."""
        self.inner = Scheduler(network, pathfinder)
        self.left = ok_turns

    def decide_moves(self, state: SimulationState) -> list[MoveOrder]:
        """Delegate while turns are left; then order no move."""
        if self.left == 0:
            return []
        self.left -= 1
        return self.inner.decide_moves(state)


class TtyStringIO(io.StringIO):
    """A StringIO that reports itself as a terminal."""

    def isatty(self) -> bool:
        """Claim to be a terminal."""
        return True


class NetworkFactory(Protocol):
    """Signature of the ``make_network`` fixture."""

    def __call__(
        self,
        edges: str,
        types: dict[str, ZoneType] | None = None,
        start: str = "s",
        end: str = "g",
        isolated: tuple[str, ...] = (),
        capacity: dict[str, int] | None = None,
        links: dict[str, int] | None = None,
    ) -> Network:
        """Build a network from a compact edge description."""
        ...


def build_network(
    edges: str,
    types: dict[str, ZoneType] | None = None,
    start: str = "s",
    end: str = "g",
    isolated: tuple[str, ...] = (),
    capacity: dict[str, int] | None = None,
    links: dict[str, int] | None = None,
) -> Network:
    """Build a network from space separated ``a-b`` edges.

    Zones are registered in order of first appearance (start and end are
    always created, even without connections), and connections in the
    order they are written, which is the declaration order the
    pathfinder must keep and the name a connection is printed with.

    Args:
        edges: Connections such as ``"s-a a-g"``.
        types: Zone types by name; zones missing here are NORMAL.
        start: Name of the start zone.
        end: Name of the end zone.
        isolated: Extra zones with no connection.
        capacity: ``max_drones`` of hubs by name; hubs missing here get 1,
            the parser's default. Start and end always get None, as the
            parser normalizes them.
        links: ``max_link_capacity`` by connection name (``"s-a"``, as
            written in ``edges``); connections missing here get 1.
    """
    zone_types = types or {}
    zone_capacity = capacity or {}
    link_capacity = links or {}
    pairs = [tuple(edge.split("-")) for edge in edges.split()]
    names: list[str] = []
    for name in [start, end, *(n for p in pairs for n in p), *isolated]:
        if name not in names:
            names.append(name)

    network = Network()
    for name in names:
        max_drones: int | None = None
        if name == start:
            role = ZoneRole.START
        elif name == end:
            role = ZoneRole.END
        else:
            role = ZoneRole.HUB
            max_drones = zone_capacity.get(name, 1)
        network.add_zone(
            Zone(
                name=name,
                x=0,
                y=0,
                zone_type=zone_types.get(name, ZoneType.NORMAL),
                role=role,
                max_drones=max_drones,
            )
        )
    for zone_a, zone_b in pairs:
        network.add_connection(
            Connection(
                zone_a=zone_a,
                zone_b=zone_b,
                max_link_capacity=link_capacity.get(f"{zone_a}-{zone_b}", 1),
            )
        )
    return network


SchedulerMaker = Callable[[Network, Pathfinder], MoveDecider]


@pytest.fixture
def stuck_after() -> Callable[[int], SchedulerMaker]:
    """Return ``ok_turns -> make_scheduler`` for ``StuckScheduler``.

    Pass the result as ``Application(..., make_scheduler=...)``.
    """

    def make(ok_turns: int) -> SchedulerMaker:
        return functools.partial(StuckScheduler, ok_turns=ok_turns)

    return make


@pytest.fixture
def make_network() -> NetworkFactory:
    """Return a factory that builds small networks in one line."""
    return build_network


@pytest.fixture
def write_map(tmp_path: Path) -> Callable[[str], Path]:
    """Return a function writing a map file under tmp_path.

    The map text must start with ``nb_drones: <n>`` on its physical first
    line (decisions 2026-10-16).
    """

    def write(text: str) -> Path:
        path = tmp_path / "map.txt"
        path.write_text(text)
        return path

    return write


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
def load_world(
    write_map: Callable[[str], Path],
) -> Callable[[str], World]:
    """Return a function writing a map and parsing it into a World."""

    def load(text: str) -> World:
        return MapParser(write_map(text)).parse()

    return load


@pytest.fixture
def place() -> Callable[..., SimulationState]:
    """Return the ``place_drones`` helper."""
    return place_drones


@pytest.fixture
def snapshot() -> Callable[[SimulationState], Snapshot]:
    """Return the ``take_snapshot`` helper."""
    return take_snapshot


@pytest.fixture
def subject_map() -> str:
    """Return the subject's sample map (the one before chapter VII.5)."""
    return SUBJECT_SAMPLE_MAP


@pytest.fixture
def subject_output() -> list[str]:
    """Return the subject's sample output (seven lines).

    This is the example printed in the subject, not the real scheduler's
    output (see ``scheduler_output``).
    """
    return list(SAMPLE_OUTPUT)


@pytest.fixture
def scheduler_output() -> list[str]:
    """Return the real scheduler's five output lines for the sample map."""
    return list(SCHEDULER_OUTPUT)


@pytest.fixture
def restricted_only_map() -> str:
    """Return the sample map with corridorA blocked (roof1 only)."""
    return RESTRICTED_ONLY_MAP


@pytest.fixture
def tty_stream() -> Callable[..., TtyStringIO]:
    """Return a factory for terminal-like streams, for input or output."""

    def make(text: str = "") -> TtyStringIO:
        return TtyStringIO(text)

    return make


def open_archive() -> tarfile.TarFile:
    """Open the provided maps, failing loudly if the archive is missing."""
    if not MAPS_ARCHIVE.is_file():
        pytest.fail(
            "maps.tar.gz is required at the repository root, next to "
            "tests/ (the provided maps are read from it)"
        )
    return tarfile.open(MAPS_ARCHIVE, "r:gz")


def read_provided_map(member: str) -> str:
    """Return a provided map without its leading comments and blank lines.

    Only those are removed, so that ``nb_drones`` is on the physical first
    line as the parser requires (decisions 2026-10-16); comments further
    down are kept, the parser handles them.
    """
    with open_archive() as archive:
        stream = archive.extractfile(member)
        assert stream is not None, f"{member} is not a file"
        text = stream.read().decode("utf-8")
    lines = text.splitlines(keepends=True)
    while lines and lines[0].strip()[:1] in ("", "#"):
        lines.pop(0)
    return "".join(lines)


@pytest.fixture
def maps_archive() -> Callable[[], tarfile.TarFile]:
    """Return a function opening ``maps.tar.gz`` (fails if it is missing)."""
    return open_archive


@pytest.fixture
def provided_map() -> Callable[[str], str]:
    """Return a function reading one provided map by archive member.

    The member is a path such as ``maps/easy/01_linear_path.txt``; the
    text comes back with its leading comments and blank lines removed.
    """
    return read_provided_map
