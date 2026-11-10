"""Tests for scheduler (Departure, plan_departures, Scheduler).

``plan_departures`` never looks at the held map, so its tests build the
``FlowMap`` by hand over an empty network. The broken flow maps of the
error tests reach the real ``Scheduler`` through ``fixed_scheduler``.
"""

import dataclasses
from pathlib import Path
from typing import Callable

import pytest

from engine import MoveOrder, SimulationState, TurnResolver
from errors import SimulationError
from map_parser import MapParser
from pathfinder import FlowMap, Pathfinder, Route
from scheduler import Departure, Scheduler, plan_departures
from world import Network, ZoneType

MakeNetwork = Callable[..., Network]
WriteMap = Callable[[str], Path]
RealScheduler = Callable[[Network], Scheduler]
FixedScheduler = Callable[[Network, FlowMap], Scheduler]
Place = Callable[..., SimulationState]
Orders = list[tuple[int, str]]

R = ZoneType.RESTRICTED


def route(text: str, rate: int, turns: int) -> Route:
    """Return the route through the space separated zones of ``text``."""
    return Route(tuple(text.split()), rate, turns)


def summary(departures: dict[int, Departure]) -> dict[int, tuple[str, int]]:
    """Return each drone's first zone entered and its departure turn."""
    return {
        drone_id: (departure.route.zones[1], departure.turn)
        for drone_id, departure in departures.items()
    }


def plan(
    make_network: MakeNetwork,
    routes: tuple[Route, ...],
    last: int,
    nb_drones: int,
) -> dict[int, tuple[str, int]]:
    """Run ``plan_departures`` on a hand-made flow map; summarize it."""
    flow_map = FlowMap(make_network(""), routes, last)
    return summary(plan_departures(flow_map, nb_drones))


def play(
    scheduler: Scheduler, network: Network, nb_drones: int
) -> list[Orders]:
    """Play a run to the end; return each turn's orders, in order."""
    resolver = TurnResolver(network)
    state = SimulationState(network, nb_drones)
    turns: list[Orders] = []
    while not state.is_complete:
        assert state.turn_number < 100
        orders = scheduler.decide_moves(state)
        turns.append([(order.drone_id, order.zone_name) for order in orders])
        resolver.resolve(state, orders)
    return turns


# --- plan_departures --------------------------------------------------


def test_one_route_of_rate_one(make_network: MakeNetwork) -> None:
    """PD01: one seat per turn."""
    assert plan(make_network, (route("s a g", 1, 2),), 3, 2) == {
        1: ("a", 1), 2: ("a", 2)
    }


def test_seats_are_rate_times_turns(make_network: MakeNetwork) -> None:
    """PD02: drones leave on turns 1 .. T - turns + 1, ``rate`` a turn."""
    routes = (route("s a g", 2, 2),)
    assert plan(make_network, routes, 3, 4) == {
        1: ("a", 1), 2: ("a", 1), 3: ("a", 2), 4: ("a", 2)
    }
    assert plan(make_network, routes, 3, 3) == {
        1: ("a", 1), 2: ("a", 1), 3: ("a", 2)
    }


def test_earliest_arrival_then_earliest_departure(
    make_network: MakeNetwork,
) -> None:
    """PD03: D2 and D3 both arrive on turn 3; leaving on turn 1 by r
    comes before leaving on turn 2 by a."""
    routes = (route("s a g", 1, 2), route("s r g", 1, 3))
    assert plan(make_network, routes, 3, 3) == {
        1: ("a", 1), 2: ("r", 1), 3: ("a", 2)
    }


def test_ties_go_by_route_order(make_network: MakeNetwork) -> None:
    """PD04: the order of ``routes`` decides, not the zone names."""
    first = route("s a g", 1, 2)
    second = route("s b g", 1, 2)
    assert plan(make_network, (first, second), 2, 2) == {
        1: ("a", 1), 2: ("b", 1)
    }
    assert plan(make_network, (second, first), 2, 2) == {
        1: ("b", 1), 2: ("a", 1)
    }


def test_route_too_long_for_the_last_turn_has_no_seat(
    make_network: MakeNetwork,
) -> None:
    """PD05: a route that cannot arrive by T gets no seat."""
    routes = (route("s a g", 1, 2), route("s r g", 1, 10))
    assert plan(make_network, routes, 3, 2) == {1: ("a", 1), 2: ("a", 2)}


def test_no_drones(make_network: MakeNetwork) -> None:
    """PD06: no drones, no departures."""
    assert plan(make_network, (), 0, 0) == {}


def test_too_few_seats_raise(make_network: MakeNetwork) -> None:
    """PD07: a wrong flow map is reported instead of leaving drones out."""
    with pytest.raises(SimulationError) as excinfo:
        plan(make_network, (route("s a g", 1, 2),), 2, 2)
    assert str(excinfo.value) == "the flow map has 1 seats for 2 drones"

    with pytest.raises(SimulationError) as excinfo:
        plan(make_network, (), 0, 1)
    assert str(excinfo.value) == "the flow map has 0 seats for 1 drones"


def subject_departures(
    write_map: WriteMap, subject_map: str
) -> dict[int, Departure]:
    """Return the departures on the subject's example (five drones)."""
    network = MapParser(write_map(subject_map)).parse().network
    return plan_departures(Pathfinder(network).flow_map(5), 5)


def test_subject_map_departures(
    write_map: WriteMap, subject_map: str
) -> None:
    """PD08: D2 and D4 go round by roof1 (``scheduler_output``)."""
    assert summary(subject_departures(write_map, subject_map)) == {
        1: ("corridorA", 1),
        2: ("roof1", 1),
        3: ("corridorA", 2),
        4: ("roof1", 2),
        5: ("corridorA", 3),
    }


def test_departure_value_is_frozen(
    write_map: WriteMap, subject_map: str
) -> None:
    """PD09: a departure is a plain frozen value."""
    departure = subject_departures(write_map, subject_map)[2]

    assert departure == Departure(
        route=Route(("hub", "roof1", "roof2", "goal"), 1, 4), turn=1
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(departure, "turn", 2)


# --- Scheduler --------------------------------------------------------


def test_flow_map_is_built_on_the_first_decision(
    make_network: MakeNetwork, real_scheduler: RealScheduler
) -> None:
    """SC01: no flow map before the first turn is decided."""
    network = make_network("s-a a-g")
    scheduler = real_scheduler(network)
    assert scheduler.flow_map is None

    scheduler.decide_moves(SimulationState(network, 2))

    flow_map = scheduler.flow_map
    assert flow_map is not None
    assert flow_map.routes == (route("s a g", 1, 2),)
    assert flow_map.last_turn == 3


def test_pull_order_is_nearest_to_the_end_first(
    make_network: MakeNetwork, real_scheduler: RealScheduler
) -> None:
    """SC02: orders are listed by the zone pulling, end side first, not
    by drone_id."""
    network = make_network("s-a a-b b-g")

    assert play(real_scheduler(network), network, 3) == [
        [(1, "a")],
        [(1, "b"), (2, "a")],
        [(1, "g"), (2, "b"), (3, "a")],
        [(2, "g"), (3, "b")],
        [(3, "g")],
    ]


def test_subject_map_orders(
    write_map: WriteMap, subject_map: str, real_scheduler: RealScheduler
) -> None:
    """SC03: the pull order is goal, roof2, tunnelB, roof1, corridorA
    (same turns left: declaration order of the held map)."""
    network = MapParser(write_map(subject_map)).parse().network

    assert play(real_scheduler(network), network, 5) == [
        [(2, "roof1"), (1, "corridorA")],
        [(1, "tunnelB"), (4, "roof1"), (3, "corridorA")],
        [(1, "goal"), (2, "roof2"), (3, "tunnelB"), (5, "corridorA")],
        [(2, "goal"), (3, "goal"), (4, "roof2"), (5, "tunnelB")],
        [(4, "goal"), (5, "goal")],
    ]


def test_drones_wait_in_the_start_zone_for_their_turn(
    make_network: MakeNetwork, real_scheduler: RealScheduler
) -> None:
    """SC04: D2 leaves on turn 2, so it gets no order on turn 1."""
    network = make_network("s-a a-g")
    orders = real_scheduler(network).decide_moves(SimulationState(network, 2))

    assert orders == [MoveOrder(1, "a")]


def test_drones_in_flight_get_no_order(
    make_network: MakeNetwork, real_scheduler: RealScheduler, place: Place
) -> None:
    """SC05: the resolver lands D1 by itself; D2 leaves on turn 2."""
    network = make_network("s-r r-g", types={"r": R})
    state = place(network, 2, flying={1: ("s", "r")})
    state.turn_number = 1

    assert real_scheduler(network).decide_moves(state) == [MoveOrder(2, "r")]


def test_restricted_orders_name_the_zone(
    make_network: MakeNetwork,
    real_scheduler: RealScheduler,
    fmt: Callable[..., str],
) -> None:
    """SC06: the order names the restricted zone; the resolver prints the
    connection."""
    network = make_network("s-r r-g", types={"r": R})
    scheduler = real_scheduler(network)
    resolver = TurnResolver(network)
    state = SimulationState(network, 2)
    orders: list[Orders] = []
    lines: list[str] = []
    while not state.is_complete:
        assert state.turn_number < 100
        turn = scheduler.decide_moves(state)
        orders.append([(order.drone_id, order.zone_name) for order in turn])
        lines.append(fmt(resolver.resolve(state, turn)))

    assert orders == [[(1, "r")], [(2, "r")], [(1, "g")], [(2, "g")]]
    assert lines == ["D1-s-r", "D1-r D2-s-r", "D1-g D2-r", "D2-g"]


def test_delivered_drones_get_no_order(
    make_network: MakeNetwork, real_scheduler: RealScheduler
) -> None:
    """SC07: only the active drones are pulled."""
    network = make_network("s-a a-g")
    scheduler = real_scheduler(network)
    resolver = TurnResolver(network)
    state = SimulationState(network, 2)
    for _ in range(2):
        resolver.resolve(state, scheduler.decide_moves(state))
    assert state.drones[1].is_delivered

    assert scheduler.decide_moves(state) == [MoveOrder(2, "g")]


def test_deciding_twice_changes_nothing(
    make_network: MakeNetwork,
    real_scheduler: RealScheduler,
    snapshot: Callable[[SimulationState], object],
) -> None:
    """SC08: the scheduler only reads the state."""
    network = make_network("s-a a-g")
    scheduler = real_scheduler(network)
    state = SimulationState(network, 2)
    before = snapshot(state)

    assert scheduler.decide_moves(state) == [MoveOrder(1, "a")]
    assert scheduler.decide_moves(state) == [MoveOrder(1, "a")]
    assert snapshot(state) == before
    assert [d.history for d in state.drones.values()] == [["s"], ["s"]]


def test_turn_zero_plans_again(
    make_network: MakeNetwork, real_scheduler: RealScheduler
) -> None:
    """SC09: a new run is planned again, even with another drone count."""
    network = make_network("s-a a-g")
    scheduler = real_scheduler(network)
    scheduler.decide_moves(SimulationState(network, 2))
    first = scheduler.flow_map
    assert first is not None and first.last_turn == 3

    scheduler.decide_moves(SimulationState(network, 3))

    second = scheduler.flow_map
    assert second is not None and second.last_turn == 4
    assert second is not first


def test_flow_map_built_only_on_turn_zero(
    make_network: MakeNetwork, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC10: every call on turn 0 plans; later turns never do."""
    network = make_network("s-a a-g")
    pathfinder = Pathfinder(network)
    build = pathfinder.flow_map
    calls: list[int] = []

    def recording(nb_drones: int) -> FlowMap:
        calls.append(nb_drones)
        return build(nb_drones)

    monkeypatch.setattr(pathfinder, "flow_map", recording)
    scheduler = Scheduler(network, pathfinder)
    resolver = TurnResolver(network)
    state = SimulationState(network, 2)
    while not state.is_complete:
        assert state.turn_number < 100
        scheduler.decide_moves(state)
        resolver.resolve(state, scheduler.decide_moves(state))
    assert calls == [2, 2]

    play(scheduler, network, 2)
    assert calls == [2, 2, 2]


def test_missed_departure_raises(
    make_network: MakeNetwork, real_scheduler: RealScheduler
) -> None:
    """SC11: a drone still in the start zone after its turn to leave."""
    network = make_network("s-a a-g")
    state = SimulationState(network, 2)
    state.turn_number = 1

    with pytest.raises(SimulationError) as excinfo:
        real_scheduler(network).decide_moves(state)
    assert str(excinfo.value) == "D1 missed its turn 1 to leave"


def test_drone_without_a_route_raises(
    make_network: MakeNetwork, real_scheduler: RealScheduler, place: Place
) -> None:
    """SC12: more drones than were planned for (D1 is pulled first)."""
    network = make_network("s-a a-g")
    scheduler = real_scheduler(network)
    scheduler.decide_moves(SimulationState(network, 1))
    state = place(network, 2, at={1: "a"})
    state.turn_number = 1

    with pytest.raises(SimulationError) as excinfo:
        scheduler.decide_moves(state)
    assert str(excinfo.value) == "D2 has no route"


def test_drone_off_its_route_raises(
    make_network: MakeNetwork, real_scheduler: RealScheduler, place: Place
) -> None:
    """SC13: the history does not start like the route (s a g)."""
    network = make_network("s-a a-g s-b b-g")
    state = place(network, 1, at={1: "b"})
    state.turn_number = 1

    with pytest.raises(SimulationError) as excinfo:
        real_scheduler(network).decide_moves(state)
    assert str(excinfo.value) == "D1 is in 'b', off its route"


def test_drone_at_the_end_of_its_route_raises(
    make_network: MakeNetwork, real_scheduler: RealScheduler, place: Place
) -> None:
    """SC14: the whole route is behind an undelivered drone."""
    network = make_network("s-a a-g")
    state = place(network, 1, at={1: "a"})
    state.turn_number = 1
    state.drones[1].history.append("g")

    with pytest.raises(SimulationError) as excinfo:
        real_scheduler(network).decide_moves(state)
    assert str(excinfo.value) == "D1 is in 'a', off its route"


def test_going_back_raises(
    make_network: MakeNetwork, fixed_scheduler: FixedScheduler, place: Place
) -> None:
    """SC15: only a hand-made route passes a zone twice."""
    network = make_network("s-a a-b a-g")
    scheduler = fixed_scheduler(
        network,
        FlowMap(network, (Route(("s", "a", "b", "a", "g"), 1, 4),), 4),
    )
    state = place(network, 1, at={1: "a"})
    state.enter_zone(1, "b")
    assert state.drones[1].history == ["s", "a", "b"]
    state.turn_number = 2

    with pytest.raises(SimulationError) as excinfo:
        scheduler.decide_moves(state)
    assert str(excinfo.value) == "D1 would go back into 'a'"


def test_missing_held_connection_raises(
    make_network: MakeNetwork, fixed_scheduler: FixedScheduler, place: Place
) -> None:
    """SC16: the held map lacks the connection of the route."""
    network = make_network("s-a a-g")
    scheduler = fixed_scheduler(
        network, FlowMap(make_network("s-a"), (route("s a g", 1, 2),), 2)
    )
    state = place(network, 1, at={1: "a"})
    state.turn_number = 1

    with pytest.raises(SimulationError) as excinfo:
        scheduler.decide_moves(state)
    assert str(excinfo.value) == "the flow map has no connection 'a'-'g'"


def wide_network(make_network: MakeNetwork) -> Network:
    """Return ``s-a a-g`` with room for two drones per turn (SC17-SC19)."""
    return make_network(
        "s-a a-g", capacity={"a": 2}, links={"s-a": 2, "a-g": 2}
    )


def test_full_held_connection_raises(
    make_network: MakeNetwork, fixed_scheduler: FixedScheduler
) -> None:
    """SC17: two drones on a held connection of capacity 1."""
    network = wide_network(make_network)
    held = make_network("s-a a-g", capacity={"a": 2})
    scheduler = fixed_scheduler(
        network, FlowMap(held, (route("s a g", 2, 2),), 2)
    )

    with pytest.raises(SimulationError) as excinfo:
        scheduler.decide_moves(SimulationState(network, 2))
    assert str(excinfo.value) == "D2: connection 's-a' of the flow map is full"


def test_full_held_zone_raises(
    make_network: MakeNetwork, fixed_scheduler: FixedScheduler
) -> None:
    """SC18: the connection check passes, then the zone check fails."""
    network = wide_network(make_network)
    held = make_network("s-a a-g", links={"s-a": 2, "a-g": 2})
    scheduler = fixed_scheduler(
        network, FlowMap(held, (route("s a g", 2, 2),), 2)
    )

    with pytest.raises(SimulationError) as excinfo:
        scheduler.decide_moves(SimulationState(network, 2))
    assert str(excinfo.value) == "D2: zone 'a' of the flow map is full"


def test_too_few_seats_reach_the_scheduler(
    make_network: MakeNetwork, fixed_scheduler: FixedScheduler
) -> None:
    """SC19: the error of ``plan_departures`` comes through as it is."""
    network = wide_network(make_network)
    held = make_network("s-a a-g", links={"s-a": 2, "a-g": 2})
    scheduler = fixed_scheduler(
        network, FlowMap(held, (route("s a g", 1, 2),), 2)
    )

    with pytest.raises(SimulationError) as excinfo:
        scheduler.decide_moves(SimulationState(network, 2))
    assert str(excinfo.value) == "the flow map has 1 seats for 2 drones"


@pytest.mark.parametrize(
    ("which", "expected"),
    [("subject", 5), ("restricted_only", 8)],
)
def test_orders_pass_the_resolver(
    write_map: WriteMap,
    subject_map: str,
    restricted_only_map: str,
    real_scheduler: RealScheduler,
    which: str,
    expected: int,
) -> None:
    """SC20: the run ends in ``flow_map.last_turn`` turns, every turn
    accepted by the resolver."""
    text = subject_map if which == "subject" else restricted_only_map
    world = MapParser(write_map(text)).parse()
    scheduler = real_scheduler(world.network)

    turns = play(scheduler, world.network, world.nb_drones)

    flow_map = scheduler.flow_map
    assert flow_map is not None
    assert len(turns) == flow_map.last_turn == expected
