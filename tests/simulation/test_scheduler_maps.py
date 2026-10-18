"""End-to-end tests of the Stage 5 Scheduler on real maps.

The subject's sample map comes from the shared fixtures. The ten maps
handed out with the subject are read from ``maps.tar.gz`` at the
repository root (tracked by git) without extracting it: only the leading
comment and blank lines are removed, so that ``nb_drones`` is on the
physical first line as the parser requires (decisions 2026-10-16).
"""

import random
import tarfile
from pathlib import Path
from typing import Callable

import pytest

from droneflow.models.drone import DroneStatus
from droneflow.models.network import Network
from droneflow.models.world import World
from droneflow.models.zone import ZoneType
from droneflow.output.formatter import TurnLogFormatter
from droneflow.parsing.map_parser import MapParser
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.engine import SimulationEngine, default_turn_limit
from droneflow.simulation.scheduler import Scheduler
from droneflow.simulation.state import Move, SimulationState
from droneflow.simulation.turn_resolver import TurnResolver

WriteMap = Callable[[str], Path]
MakeNetwork = Callable[..., Network]

R = ZoneType.RESTRICTED

MAPS_ARCHIVE = Path(__file__).resolve().parents[2] / "maps.tar.gz"

# (member in the archive, nb_drones, turn limit, where the limit comes from)
PROVIDED_MAPS = [
    ("maps/easy/01_linear_path.txt", 2, 6, "VII.7"),
    ("maps/easy/02_simple_fork.txt", 4, 8, "VII.7"),
    ("maps/easy/03_basic_capacity.txt", 4, 6, "VII.7"),
    ("maps/medium/01_dead_end_trap.txt", 5, 12, "VII.7"),
    ("maps/medium/02_circular_loop.txt", 6, 15, "VII.7"),
    ("maps/medium/03_priority_puzzle.txt", 5, 12, "VII.7"),
    ("maps/hard/01_maze_nightmare.txt", 8, 30, "VII.7"),
    ("maps/hard/02_capacity_hell.txt", 12, 35, "VII.7"),
    ("maps/hard/03_ultimate_challenge.txt", 15, 45, "VII.7"),
    ("maps/challenger/01_the_impossible_dream.txt", 25, 44, "IX"),
]
GRADED_MAPS = [e for e in PROVIDED_MAPS if "challenger" not in e[0]]
CHALLENGER = PROVIDED_MAPS[-1]

SUBJECT = "subject"
RESTRICTED_ONLY = "restricted_only"


def map_id(member: str) -> str:
    """Return a short test id such as ``easy/01_linear_path``."""
    return member.removeprefix("maps/").removesuffix(".txt")


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

    Comments further down are kept; the parser handles them.
    """
    with open_archive() as archive:
        stream = archive.extractfile(member)
        assert stream is not None, f"{member} is not a file"
        text = stream.read().decode("utf-8")
    lines = text.splitlines(keepends=True)
    while lines and lines[0].strip()[:1] in ("", "#"):
        lines.pop(0)
    return "".join(lines)


def run_engine(world: World) -> list[list[Move]]:
    """Run the real scheduler with the engine's default turn limit."""
    engine = SimulationEngine(
        world, Scheduler(world.network, Pathfinder(world.network))
    )
    turns = engine.run()
    assert engine.state.is_complete
    assert engine.state.delivered_count == world.nb_drones
    return turns


def run_checked(world: World) -> list[list[Move]]:
    """Play the turn loop by hand, checking the scheduler every turn.

    Each turn: one order per drone, only for drones standing in zones,
    each a shortest next hop that lowers the distance, all accepted by the
    resolver, at least one move, and all within the default turn limit.
    """
    network = world.network
    pathfinder = Pathfinder(network)
    scheduler = Scheduler(network, pathfinder)
    resolver = TurnResolver(network)
    state = SimulationState(network, world.nb_drones)
    limit = default_turn_limit(world)
    turns: list[list[Move]] = []
    while not state.is_complete:
        assert state.turn_number < limit, f"not finished in {limit} turns"
        orders = scheduler.decide_moves(state)
        ids = [order.drone_id for order in orders]
        assert len(ids) == len(set(ids)), f"two orders for one drone: {ids}"
        for order in orders:
            drone = state.drones[order.drone_id]
            assert drone.status is DroneStatus.AT_ZONE
            here = drone.current_zone
            assert here is not None
            shortest = [hop.zone.name for hop in pathfinder.next_hops(here)]
            assert order.zone in shortest, f"D{order.drone_id} detours"
            after = pathfinder.distance(order.zone)
            before = pathfinder.distance(here)
            assert after is not None and before is not None
            assert after < before
        moves = resolver.resolve(state, orders)
        assert moves, f"turn {state.turn_number}: no drone moved"
        turns.append(moves)
    assert state.delivered_count == world.nb_drones
    return turns


@pytest.fixture
def load_world(
    write_map: WriteMap, subject_map: str, restricted_only_map: str
) -> Callable[[str], World]:
    """Return a loader parsing a map given by key or archive member."""
    texts = {SUBJECT: subject_map, RESTRICTED_ONLY: restricted_only_map}

    def load(source: str) -> World:
        text = texts[source] if source in texts else read_provided_map(source)
        return MapParser(write_map(text)).parse()

    return load


Load = Callable[[str], World]


# --- the subject's sample map -----------------------------------------


def test_subject_sample_map_output(
    load_world: Load,
    subject_output: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """R01: the real scheduler prints the subject's seven lines exactly."""
    TurnLogFormatter().emit(run_engine(load_world(SUBJECT)))

    assert capsys.readouterr().out.splitlines() == subject_output


def test_restricted_only_map_output(
    load_world: Load, capsys: pytest.CaptureFixture[str]
) -> None:
    """R02: through restricted roof1 only, the run takes eight turns.

    The drone landing in roof1 is planned to leave it (for roof2) on the
    next turn, so one drone can take off toward roof1 every turn.
    """
    TurnLogFormatter().emit(run_engine(load_world(RESTRICTED_ONLY)))

    assert capsys.readouterr().out.splitlines() == [
        "D1-hub-roof1",
        "D1-roof1 D2-hub-roof1",
        "D1-roof2 D2-roof1 D3-hub-roof1",
        "D1-goal D2-roof2 D3-roof1 D4-hub-roof1",
        "D2-goal D3-roof2 D4-roof1 D5-hub-roof1",
        "D3-goal D4-roof2 D5-roof1",
        "D4-goal D5-roof2",
        "D5-goal",
    ]


# --- every turn on every map ------------------------------------------


@pytest.mark.parametrize(
    "source",
    [SUBJECT, RESTRICTED_ONLY, *(entry[0] for entry in PROVIDED_MAPS)],
    ids=[SUBJECT, RESTRICTED_ONLY, *(map_id(e[0]) for e in PROVIDED_MAPS)],
)
def test_every_turn_is_sound(load_world: Load, source: str) -> None:
    """R03: legal, shortest, progressing orders every turn until done."""
    assert run_checked(load_world(source))


# --- turn counts ------------------------------------------------------


@pytest.mark.parametrize(
    ("member", "nb_drones", "limit"),
    [entry[:3] for entry in GRADED_MAPS],
    ids=[map_id(entry[0]) for entry in GRADED_MAPS],
)
def test_provided_map_meets_target(
    load_world: Load, member: str, nb_drones: int, limit: int
) -> None:
    """R04: every drone arrives within the VII.7 target turn count."""
    world = load_world(member)
    assert world.nb_drones == nb_drones

    assert len(run_engine(world)) <= limit


def test_challenger_beats_reference(load_world: Load) -> None:
    """R05: all 25 drones arrive in fewer than 45 turns (IX bonus)."""
    member, nb_drones, _, _ = CHALLENGER
    world = load_world(member)
    assert world.nb_drones == nb_drones

    assert len(run_engine(world)) < 45


def test_provided_maps_archive() -> None:
    """R06: the archive holds exactly the ten maps with these drone counts."""
    with open_archive() as archive:
        members = sorted(
            info.name for info in archive.getmembers()
            if info.isfile() and info.name.endswith(".txt")
        )
    assert members == sorted(entry[0] for entry in PROVIDED_MAPS)
    for member, nb_drones, _, _ in PROVIDED_MAPS:
        first = read_provided_map(member).splitlines()[0]
        assert first.split() == ["nb_drones:", str(nb_drones)], member


# --- determinism and lower bound --------------------------------------


@pytest.mark.parametrize(
    "source",
    [SUBJECT, "maps/hard/03_ultimate_challenge.txt"],
    ids=[SUBJECT, "hard/03_ultimate_challenge"],
)
def test_runs_are_deterministic(load_world: Load, source: str) -> None:
    """R07: two runs on separately parsed worlds give the same moves."""
    assert run_engine(load_world(source)) == run_engine(load_world(source))


@pytest.mark.parametrize(
    "source",
    [SUBJECT, *(entry[0] for entry in GRADED_MAPS)],
    ids=[SUBJECT, *(map_id(entry[0]) for entry in GRADED_MAPS)],
)
def test_turns_not_below_single_drone_bound(
    load_world: Load, source: str
) -> None:
    """R08: no run is shorter than one drone's shortest path."""
    world = load_world(source)
    start = world.network.start_zone.name
    bound = Pathfinder(world.network).distance(start)
    assert bound is not None

    turns = len(run_engine(world))

    assert turns >= bound
    if source == SUBJECT:
        assert turns == 7
    if source.endswith("01_linear_path.txt"):
        assert turns >= 3


# --- planned moves and evictions (timed reservation) ------------------


def output_lines(world: World) -> list[str]:
    """Run the engine and return the printed lines; check run_checked too.

    ``run_checked`` plays the same map by hand with the per-turn checks
    of R03 and must print the same lines.
    """
    format_turn = TurnLogFormatter().format_turn
    lines = [format_turn(moves) for moves in run_engine(world)]
    assert [format_turn(moves) for moves in run_checked(world)] == lines
    return lines


def test_single_restricted_zone(make_network: MakeNetwork) -> None:
    """R09: D1 is planned to leave r as D2 lands (the old rules took 5)."""
    network = make_network("s-r r-g", types={"r": R})

    assert output_lines(World(network, 2)) == [
        "D1-s-r",
        "D1-r D2-s-r",
        "D1-g D2-r",
        "D2-g",
    ]


@pytest.mark.parametrize(
    ("edges", "capacity", "links", "expected"),
    [
        pytest.param(
            "s-r r-g",
            {"r": 2},
            {"s-r": 2},
            [
                "D1-s-r D2-s-r",
                "D1-r D2-r D3-s-r",
                "D1-g D3-r D4-s-r",
                "D2-g D4-r",
                "D3-g",
                "D4-g",
            ],
            id="K1",
        ),
        pytest.param(
            "s-r r-a a-g",
            {"r": 2, "a": 1},
            {"s-r": 2, "r-a": 2},
            [
                "D1-s-r D2-s-r",
                "D1-r D2-r D3-s-r",
                "D1-a D3-r D4-s-r",
                "D1-g D2-a D4-r",
                "D2-g D3-a",
                "D3-g D4-a",
                "D4-g",
            ],
            id="K2",
        ),
    ],
)
def test_wide_restricted_zone_with_narrow_exit(
    make_network: MakeNetwork,
    edges: str,
    capacity: dict[str, int],
    links: dict[str, int],
    expected: list[str],
) -> None:
    """R10: failed evictions are undone and nobody gets stuck."""
    network = make_network(
        edges, types={"r": R}, capacity=capacity, links=links
    )

    assert output_lines(World(network, 4)) == expected


def test_eviction_as_last_resort_map(make_network: MakeNetwork) -> None:
    """R11: two restricted ways; evicting only as a last resort (5 turns)."""
    network = make_network(
        "s-a a-g s-b b-g",
        types={"a": R, "b": R},
        capacity={"a": 2, "b": 3},
        links={"s-a": 2},
    )

    assert output_lines(World(network, 6)) == [
        "D1-s-a D2-s-a D3-s-b",
        "D1-a D2-a D3-b D4-s-b D5-s-a",
        "D1-g D3-g D4-b D5-a D6-s-b",
        "D2-g D4-g D6-b",
        "D5-g D6-g",
    ]


@pytest.mark.parametrize(
    ("edges", "nb_drones", "expected"),
    [
        pytest.param(
            "s-r1 r1-r2 r2-g",
            2,
            [
                "D1-s-r1",
                "D1-r1 D2-s-r1",
                "D1-r1-r2 D2-r1",
                "D1-r2 D2-r1-r2",
                "D1-g D2-r2",
                "D2-g",
            ],
            id="two",
        ),
        pytest.param(
            "s-r1 r1-r2 r2-r3 r3-g",
            3,
            [
                "D1-s-r1",
                "D1-r1 D2-s-r1",
                "D1-r1-r2 D2-r1 D3-s-r1",
                "D1-r2 D2-r1-r2 D3-r1",
                "D1-r2-r3 D2-r2 D3-r1-r2",
                "D1-r3 D2-r2-r3 D3-r2",
                "D1-g D2-r3 D3-r2-r3",
                "D2-g D3-r3",
                "D3-g",
            ],
            id="three",
        ),
        pytest.param(
            "s-r1 r1-n n-r2 r2-g",
            3,
            [
                "D1-s-r1",
                "D1-r1 D2-s-r1",
                "D1-n D2-r1 D3-s-r1",
                "D1-n-r2 D2-n D3-r1",
                "D1-r2 D2-n-r2 D3-n",
                "D1-g D2-r2 D3-n-r2",
                "D2-g D3-r2",
                "D3-g",
            ],
            id="normal-between",
        ),
    ],
)
def test_restricted_zones_in_a_row(
    make_network: MakeNetwork,
    edges: str,
    nb_drones: int,
    expected: list[str],
) -> None:
    """R12: evictions recurse through restricted zones of capacity 1."""
    network = make_network(edges, types={"r1": R, "r2": R, "r3": R})

    assert output_lines(World(network, nb_drones)) == expected


def test_rule_6_prime_map(make_network: MakeNetwork) -> None:
    """R13: D3 enters z1 on turn 7 and evicts itself (11 turns, not 12)."""
    network = make_network(
        "z3-z1 z4-z3 z3-z2 s-z4 z2-z4 z2-z0 z1-g z0-z1",
        types={"z3": R, "z4": R},
        links={"z3-z1": 2, "z3-z2": 2, "s-z4": 2},
    )

    assert output_lines(World(network, 6)) == [
        "D1-s-z4",
        "D1-z4 D2-s-z4",
        "D1-z4-z3 D2-z4 D3-s-z4",
        "D1-z3 D2-z4-z3 D3-z4 D4-s-z4",
        "D1-z1 D2-z3 D3-z2 D4-z4 D5-s-z4",
        "D1-g D2-z1 D3-z0 D4-z4-z3 D5-z4 D6-s-z4",
        "D2-g D3-z1 D4-z3 D5-z4-z3 D6-z4",
        "D3-g D4-z1 D5-z3 D6-z2",
        "D4-g D5-z1 D6-z0",
        "D5-g D6-z1",
        "D6-g",
    ]


def test_rule_7_map(make_network: MakeNetwork) -> None:
    """R14: planned moves go first, and a drone may leave before its plan."""
    network = make_network(
        "z0-g s-z1 z1-z0",
        types={"z0": R, "z1": R},
        capacity={"z0": 2, "z1": 1},
        links={"z0-g": 2, "s-z1": 2},
    )

    assert output_lines(World(network, 4)) == [
        "D1-s-z1",
        "D1-z1 D2-s-z1",
        "D1-z1-z0 D2-z1 D3-s-z1",
        "D1-z0 D2-z1-z0 D3-z1 D4-s-z1",
        "D1-g D2-z0 D3-z1-z0 D4-z1",
        "D2-g D3-z0 D4-z1-z0",
        "D3-g D4-z0",
        "D4-g",
    ]


RANDOM_SEED = 2026
RANDOM_MAPS = 300

RandomMap = tuple[
    str, dict[str, ZoneType], dict[str, int], dict[str, int], int
]


def random_map(rng: random.Random) -> RandomMap:
    """Draw a small map with many restricted hubs (R15).

    Returns the edges, the zone types, the hub capacities, the link
    capacities and the number of drones, as ``make_network`` takes them.
    A chain through every hub keeps the end reachable.
    """
    n = rng.randint(2, 8)
    hubs = [f"z{i}" for i in range(n)]
    chain = ["s", *rng.sample(hubs, n), "g"]
    pairs = list(zip(chain, chain[1:]))
    nodes = ["s", *hubs, "g"]
    for _ in range(rng.randint(0, n)):
        zone_a, zone_b = rng.sample(nodes, 2)
        if (zone_a, zone_b) not in pairs and (zone_b, zone_a) not in pairs:
            pairs.append((zone_a, zone_b))
    rng.shuffle(pairs)
    types: dict[str, ZoneType] = {}
    capacity: dict[str, int] = {}
    for hub in hubs:
        types[hub] = R if rng.random() < 0.6 else ZoneType.NORMAL
        capacity[hub] = rng.randint(1, 3)
    links = {f"{a}-{b}": rng.randint(1, 2) for a, b in pairs}
    edges = " ".join(f"{a}-{b}" for a, b in pairs)
    return edges, types, capacity, links, rng.randint(2, 10)


def test_random_restricted_maps_never_get_stuck(
    make_network: MakeNetwork,
) -> None:
    """R15: many random maps rich in restricted zones all run to the end.

    ``run_checked`` fails on any stuck drone or capacity violation, on a
    detour, on a turn without movement and past the default turn limit.
    """
    rng = random.Random(RANDOM_SEED)
    for index in range(RANDOM_MAPS):
        edges, types, capacity, links, nb_drones = random_map(rng)
        network = make_network(
            edges, types=types, capacity=capacity, links=links
        )
        restricted = sorted(name for name, t in types.items() if t is R)
        where = (
            f"map {index}: edges={edges!r} restricted={restricted} "
            f"capacity={capacity} links={links} drones={nb_drones}"
        )
        try:
            run_checked(World(network, nb_drones))
        except Exception as error:
            raise AssertionError(f"{where}: {error}") from error
