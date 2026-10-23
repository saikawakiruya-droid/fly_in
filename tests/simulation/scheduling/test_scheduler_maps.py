"""End-to-end tests of the Stage 5 Scheduler on real maps.

The subject's sample map comes from the shared fixtures. The ten maps
handed out with the subject are read from ``maps.tar.gz`` at the
repository root (tracked by git) without extracting it, by the shared
``provided_map`` and ``maps_archive`` fixtures: only the leading comment
and blank lines are removed, so that ``nb_drones`` is on the physical
first line as the parser requires (decisions 2026-10-16).
"""

import random
import tarfile
from pathlib import Path
from typing import Callable, NamedTuple

import pytest

from droneflow.models.drone import DroneStatus
from droneflow.models.network import Network
from droneflow.models.world import World
from droneflow.models.zone import ZoneType
from droneflow.output.formatter import TurnLogFormatter
from droneflow.parsing.map_parser import MapParser
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.engine import SimulationEngine, default_turn_limit
from droneflow.simulation.scheduling.scheduler import Scheduler
from droneflow.simulation.state import Move, SimulationState
from droneflow.simulation.turn_resolver import TurnResolver

WriteMap = Callable[[str], Path]
MakeNetwork = Callable[..., Network]

R = ZoneType.RESTRICTED

# (member in the archive, nb_drones, optimum turn count, where it comes
# from)
PROVIDED_MAPS = [
    ("maps/easy/01_linear_path.txt", 2, 4, "VII.6"),
    ("maps/easy/02_simple_fork.txt", 4, 4, "VII.6"),
    ("maps/easy/03_basic_capacity.txt", 4, 4, "VII.6"),
    ("maps/medium/01_dead_end_trap.txt", 5, 8, "VII.6"),
    ("maps/medium/02_circular_loop.txt", 6, 10, "VII.6"),
    ("maps/medium/03_priority_puzzle.txt", 5, 6, "VII.6"),
    ("maps/hard/01_maze_nightmare.txt", 8, 13, "VII.6"),
    ("maps/hard/02_capacity_hell.txt", 12, 16, "VII.6"),
    ("maps/hard/03_ultimate_challenge.txt", 15, 26, "VII.6"),
    ("maps/challenger/01_the_impossible_dream.txt", 25, 43, "VII.6"),
]
GRADED_MAPS = [e for e in PROVIDED_MAPS if "challenger" not in e[0]]
CHALLENGER = PROVIDED_MAPS[-1]

SUBJECT = "subject"
RESTRICTED_ONLY = "restricted_only"


def map_id(member: str) -> str:
    """Return a short test id such as ``easy/01_linear_path``."""
    return member.removeprefix("maps/").removesuffix(".txt")


def run_engine(world: World) -> list[list[Move]]:
    """Run the real scheduler with the engine's default turn limit."""
    engine = SimulationEngine(
        world, Scheduler(world.network, Pathfinder(world.network))
    )
    turns = engine.run()
    assert engine.state.is_complete
    assert engine.state.delivered_count == world.nb_drones
    return turns


class CheckedRun(NamedTuple):
    """What ``run_checked`` returns: the turns and the detours taken."""

    turns: list[list[Move]]
    detours: int


def run_checked(world: World) -> CheckedRun:
    """Play the turn loop by hand, checking the scheduler every turn.

    Each turn: one order per drone, only for drones standing in zones,
    each a shortest hop that lowers the distance, or a detour into a zone
    the drone has never been in, all accepted by the resolver, at least
    one move, and all within the default turn limit. The zones each drone
    has been in are tracked here (the start, every order's target and the
    landing target of a drone in flight). At the end no drone has taken
    more detours than the network has zones minus one, the bound that
    makes detours finite.
    """
    network = world.network
    pathfinder = Pathfinder(network)
    scheduler = Scheduler(network, pathfinder)
    resolver = TurnResolver(network)
    state = SimulationState(network, world.nb_drones)
    limit = default_turn_limit(world)
    start = network.start_zone.name
    visited = {drone_id: {start} for drone_id in state.drones}
    detours = {drone_id: 0 for drone_id in state.drones}
    turns: list[list[Move]] = []
    while not state.is_complete:
        assert state.turn_number < limit, f"not finished in {limit} turns"
        for drone in state.active_drones():
            if drone.transit_target is not None:
                visited[drone.drone_id].add(drone.transit_target)
        orders = scheduler.decide_moves(state)
        ids = [order.drone_id for order in orders]
        assert len(ids) == len(set(ids)), f"two orders for one drone: {ids}"
        for order in orders:
            drone_id = order.drone_id
            drone = state.drones[drone_id]
            assert drone.status is DroneStatus.AT_ZONE
            here = drone.current_zone
            assert here is not None
            shortest = [hop.zone.name for hop in pathfinder.next_hops(here)]
            if order.zone_name in shortest:
                after = pathfinder.distance(order.zone_name)
                before = pathfinder.distance(here)
                assert after is not None and before is not None
                assert after < before
            else:
                longer = [h.zone.name for h in pathfinder.detour_hops(here)]
                assert order.zone_name in longer, (
                    f"D{drone_id} takes neither a shortest hop nor a detour"
                )
                assert order.zone_name not in visited[drone_id], (
                    f"D{drone_id} enters {order.zone_name} again by a detour"
                )
                detours[drone_id] += 1
            visited[drone_id].add(order.zone_name)
        moves = resolver.resolve(state, orders)
        assert moves, f"turn {state.turn_number}: no drone moved"
        turns.append(moves)
    assert state.delivered_count == world.nb_drones
    bound = len(network.zones) - 1
    assert all(count <= bound for count in detours.values()), detours
    return CheckedRun(turns, sum(detours.values()))


@pytest.fixture
def load_world(
    write_map: WriteMap,
    subject_map: str,
    restricted_only_map: str,
    provided_map: Callable[[str], str],
) -> Callable[[str], World]:
    """Return a loader parsing a map given by key or archive member."""
    texts = {SUBJECT: subject_map, RESTRICTED_ONLY: restricted_only_map}

    def load(source: str) -> World:
        text = texts[source] if source in texts else provided_map(source)
        return MapParser(write_map(text)).parse()

    return load


Load = Callable[[str], World]


# --- the subject's sample map -----------------------------------------


def test_subject_sample_map_output(
    load_world: Load,
    scheduler_output: list[str],
) -> None:
    """R01: the real scheduler prints these five lines.

    Two drones go round by roof1, so the run is shorter than the seven
    lines of the subject's example.
    """
    assert output_lines(load_world(SUBJECT)) == scheduler_output


def test_restricted_only_map_output(load_world: Load) -> None:
    """R02: through restricted roof1 only, the run takes eight turns.

    The drone landing in roof1 is planned to leave it (for roof2) on the
    next turn, so one drone can take off toward roof1 every turn.
    """
    assert output_lines(load_world(RESTRICTED_ONLY)) == [
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
    """R03: legal, progressing orders every turn until done.

    Every order is a shortest hop that lowers the distance, or a detour
    into a zone the drone has never been in.
    """
    assert run_checked(load_world(source)).turns


# --- turn counts ------------------------------------------------------


@pytest.mark.parametrize(
    ("member", "nb_drones", "optimum"),
    [entry[:3] for entry in GRADED_MAPS],
    ids=[map_id(entry[0]) for entry in GRADED_MAPS],
)
def test_provided_map_reaches_optimum(
    load_world: Load, member: str, nb_drones: int, optimum: int
) -> None:
    """R04: every drone arrives within the VII.6 optimum turn count."""
    world = load_world(member)
    assert world.nb_drones == nb_drones

    assert len(run_engine(world)) <= optimum


def test_challenger_within_quarter_of_optimum(load_world: Load) -> None:
    """R05: all 25 drones arrive within 25% of the VII.6 optimum (43).

    The optimum itself (the IX bonus) is not reached: the scheduler
    takes 44 turns (R19; decisions 2026-10-23).
    """
    member, nb_drones, optimum, _ = CHALLENGER
    world = load_world(member)
    assert world.nb_drones == nb_drones

    assert len(run_engine(world)) <= optimum * 1.25


def test_provided_maps_archive(
    maps_archive: Callable[[], tarfile.TarFile],
    provided_map: Callable[[str], str],
) -> None:
    """R06: the archive holds exactly the ten maps with these drone counts."""
    with maps_archive() as archive:
        members = sorted(
            info.name for info in archive.getmembers()
            if info.isfile() and info.name.endswith(".txt")
        )
    assert members == sorted(entry[0] for entry in PROVIDED_MAPS)
    for member, nb_drones, _, _ in PROVIDED_MAPS:
        first = provided_map(member).splitlines()[0]
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
        assert turns == 5
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
    checked = run_checked(world).turns
    assert [format_turn(moves) for moves in checked] == lines
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
    move that is neither a shortest hop nor a detour into a new zone, on
    a turn without movement and past the default turn limit. Some of the
    maps must take detours, so that the detour path is exercised too.
    """
    rng = random.Random(RANDOM_SEED)
    detours = 0
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
            detours += run_checked(World(network, nb_drones)).detours
        except Exception as error:
            raise AssertionError(f"{where}: {error}") from error
    assert detours >= 1


# --- detours on real maps ---------------------------------------------

# Turn counts of the real scheduler on the provided maps (R19). They
# match the stage 5 benchmark record; when an improvement changes them,
# update this table and that record together.
PROVIDED_TURNS = {
    "maps/easy/01_linear_path.txt": 4,
    "maps/easy/02_simple_fork.txt": 4,
    "maps/easy/03_basic_capacity.txt": 4,
    "maps/medium/01_dead_end_trap.txt": 8,
    "maps/medium/02_circular_loop.txt": 10,
    "maps/medium/03_priority_puzzle.txt": 6,
    "maps/hard/01_maze_nightmare.txt": 13,
    "maps/hard/02_capacity_hell.txt": 16,
    "maps/hard/03_ultimate_challenge.txt": 26,
    "maps/challenger/01_the_impossible_dream.txt": 44,
}
# Detours taken in a whole run (R20); maps missing here take none.
DETOURS_TAKEN = {
    SUBJECT: 2,
    "maps/medium/03_priority_puzzle.txt": 2,
    "maps/hard/01_maze_nightmare.txt": 3,
}


def orders_by_turn(world: World) -> list[list[tuple[int, str]]]:
    """Play the world to the end; return each turn's orders.

    One scheduler and one resolver play every turn. The orders are kept
    in the order ``decide_moves`` gave them, as ``(drone_id, zone)``.
    """
    network = world.network
    scheduler = Scheduler(network, Pathfinder(network))
    resolver = TurnResolver(network)
    state = SimulationState(network, world.nb_drones)
    turns: list[list[tuple[int, str]]] = []
    while not state.is_complete:
        assert state.turn_number < default_turn_limit(world)
        orders = scheduler.decide_moves(state)
        turns.append([(order.drone_id, order.zone_name) for order in orders])
        resolver.resolve(state, orders)
    return turns


def test_subject_sample_map_orders(load_world: Load) -> None:
    """R16: the orders of every turn on the subject's example.

    Turn 1: D2 goes round by roof1 (4 + 0 <= 3 + 1; hub-roof1 is then
    used, so D3 to D5 wait). Turn 2: D4 follows into roof1 (4 + 1 <= 3 +
    2, counting D2 landing there) by planning D2's eviction, which comes
    first on turn 3.
    """
    assert orders_by_turn(load_world(SUBJECT)) == [
        [(1, "corridorA"), (2, "roof1")],
        [(1, "tunnelB"), (3, "corridorA"), (4, "roof1")],
        [(2, "roof2"), (1, "goal"), (3, "tunnelB"), (5, "corridorA")],
        [(2, "goal"), (3, "goal"), (5, "tunnelB"), (4, "roof2")],
        [(4, "goal"), (5, "goal")],
    ]


def test_priority_puzzle_output(load_world: Load) -> None:
    """R17: restricted detours, and fast_path (priority route) deciding
    before slow_path2 at the same distance: six turns instead of eight."""
    world = load_world("maps/medium/03_priority_puzzle.txt")

    assert output_lines(world) == [
        "D1-fast_junction D2-start-slow_path1",
        "D1-fast_path D2-slow_path1 D3-fast_junction D4-start-slow_path1",
        "D1-merge_point D2-slow_path2 D3-fast_path D4-slow_path1 "
        "D5-fast_junction",
        "D1-goal D2-merge_point D3-merge_point D4-slow_path2 D5-fast_path",
        "D2-goal D3-goal D4-merge_point D5-merge_point",
        "D4-goal D5-goal",
    ]


@pytest.mark.parametrize(
    ("nb_drones", "expected"),
    [
        (2, ["D1-a D2-s-r", "D1-g D2-r", "D2-g"]),
        (3, ["D1-a D2-s-r", "D1-g D2-r D3-a", "D2-g D3-g"]),
        (
            4,
            ["D1-a D2-s-r", "D1-g D2-r D3-a", "D2-g D3-g D4-a", "D4-g"],
        ),
    ],
    ids=["two", "three", "four"],
)
def test_small_detour_map(
    make_network: MakeNetwork, nb_drones: int, expected: list[str]
) -> None:
    """R18: s-a a-g s-r r-g with r restricted; only D2 goes round by r
    (with four drones D4 finds r's queue too long)."""
    network = make_network("s-a a-g s-r r-g", types={"r": R})

    assert output_lines(World(network, nb_drones)) == expected


@pytest.mark.parametrize(
    "member",
    [entry[0] for entry in PROVIDED_MAPS],
    ids=[map_id(entry[0]) for entry in PROVIDED_MAPS],
)
def test_provided_map_turn_counts(load_world: Load, member: str) -> None:
    """R19: the turn count of every provided map, pinned."""
    assert len(run_engine(load_world(member))) == PROVIDED_TURNS[member]


@pytest.mark.parametrize(
    "source",
    [SUBJECT, *(entry[0] for entry in PROVIDED_MAPS)],
    ids=[SUBJECT, *(map_id(entry[0]) for entry in PROVIDED_MAPS)],
)
def test_detours_taken_on_real_maps(load_world: Load, source: str) -> None:
    """R20: how many detours a whole run takes on each real map.

    This catches a change in the detour rules even when the turn counts
    of R19 stay the same.
    """
    expected = DETOURS_TAKEN.get(source, 0)

    assert run_checked(load_world(source)).detours == expected
