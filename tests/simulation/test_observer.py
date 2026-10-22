"""Tests for droneflow.simulation.observer (ObserverGroup).

The group forwards each call to its observers in order (the application
gives the engine the turn log printer and the chosen views as one
observer) and closes every observer even when closing one fails; with
several failures the last is raised and the earlier ones are chained as
``__context__`` (decisions 2026-10-17 "Stage 7 API", bugs.md 2026-10-18).
OG01 to OG05 were VC01 to VC05 of the former ``CompositeVisualizer``.
"""

from typing import Callable

import pytest

from droneflow.models.network import Network
from droneflow.models.world import World
from droneflow.pathfinding.pathfinder import Pathfinder
from droneflow.simulation.engine import SimulationEngine
from droneflow.simulation.observer import ObserverGroup
from droneflow.simulation.scheduling.scheduler import Scheduler
from droneflow.simulation.state import Move, SimulationState

MakeNetwork = Callable[..., Network]
Entry = tuple[str, str]


class LogView:
    """Log ``(name, method)`` per call; optionally fail in one method."""

    def __init__(
        self, name: str, log: list[Entry], fail: str | None = None
    ) -> None:
        self.name = name
        self.log = log
        self.fail = fail
        self.received: list[object] = []

    def begin(self, state: SimulationState) -> None:
        """Log begin and keep the state."""
        self.received.append(state)
        self._log("begin")

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Log render and keep the state and moves."""
        self.received.extend([state, moves])
        self._log("render")

    def close(self) -> None:
        """Log close."""
        self._log("close")

    def _log(self, method: str) -> None:
        self.log.append((self.name, method))
        if self.fail == method:
            raise RuntimeError(self.name)


@pytest.fixture
def state(make_network: MakeNetwork) -> SimulationState:
    """Return the initial state of 1 drone over ``s-a a-g``."""
    return SimulationState(make_network("s-a a-g"), 1)


def test_calls_are_forwarded_in_order(state: SimulationState) -> None:
    """OG01: each call goes to every observer, in the observers' order."""
    log: list[Entry] = []
    a, b = LogView("a", log), LogView("b", log)
    moves = [Move(1, "a")]
    group = ObserverGroup([a, b])

    group.begin(state)
    group.render(state, moves)
    group.close()

    assert log == [
        ("a", "begin"), ("b", "begin"),
        ("a", "render"), ("b", "render"),
        ("a", "close"), ("b", "close"),
    ]
    for view in (a, b):
        assert view.received[0] is state
        assert view.received[1] is state
        assert view.received[2] is moves


def test_one_failing_close_still_closes_the_rest() -> None:
    """OG02: the failure is raised after every observer is closed."""
    log: list[Entry] = []
    group = ObserverGroup([LogView("a", log, fail="close"), LogView("b", log)])

    with pytest.raises(RuntimeError, match="^a$"):
        group.close()
    assert log == [("a", "close"), ("b", "close")]


def test_several_failing_closes_are_chained() -> None:
    """OG03: the last failure is raised, the earlier ones as context."""
    log: list[Entry] = []
    group = ObserverGroup([LogView(name, log, fail="close") for name in "abc"])

    with pytest.raises(RuntimeError, match="^c$") as excinfo:
        group.close()
    assert log == [("a", "close"), ("b", "close"), ("c", "close")]
    context_b = excinfo.value.__context__
    assert isinstance(context_b, RuntimeError)
    assert str(context_b) == "b"
    context_a = context_b.__context__
    assert isinstance(context_a, RuntimeError)
    assert str(context_a) == "a"
    assert context_a.__context__ is None


def test_no_observers(state: SimulationState) -> None:
    """OG04: with no observers every call does nothing."""
    group = ObserverGroup([])

    group.begin(state)
    group.render(state, [Move(1, "a")])
    group.close()


def test_failing_render_propagates(state: SimulationState) -> None:
    """OG05: a render failure stops the round; close still closes all."""
    log: list[Entry] = []
    group = ObserverGroup(
        [LogView("a", log, fail="render"), LogView("b", log)]
    )

    with pytest.raises(RuntimeError, match="^a$"):
        group.render(state, [Move(1, "a")])
    assert log == [("a", "render")]

    group.close()
    assert log == [("a", "render"), ("a", "close"), ("b", "close")]


def test_the_given_sequence_is_copied() -> None:
    """OG06: observers added to the caller's list later are not called;
    ``observers`` is a list of its own, from a tuple too."""
    log: list[Entry] = []
    a = LogView("a", log)
    src = [a]
    group = ObserverGroup(src)

    src.append(LogView("b", log))
    group.close()

    assert log == [("a", "close")]
    assert isinstance(group.observers, list)
    assert group.observers is not src
    assert group.observers == [a]

    x, y = LogView("x", log), LogView("y", log)
    from_tuple = ObserverGroup((x, y))
    assert isinstance(from_tuple.observers, list)
    assert from_tuple.observers == [x, y]


def test_with_the_engine(make_network: MakeNetwork) -> None:
    """OG07: the engine sees one observer; each call reaches every observer
    in order (two turns of one drone over ``s-a a-g``)."""
    network = make_network("s-a a-g")
    log: list[Entry] = []
    group = ObserverGroup([LogView("a", log), LogView("b", log)])
    engine = SimulationEngine(
        World(network, 1), Scheduler(network, Pathfinder(network))
    )

    turns = engine.run(group)

    assert len(turns) == 2
    assert log == [
        ("a", "begin"), ("b", "begin"),
        ("a", "render"), ("b", "render"),
        ("a", "render"), ("b", "render"),
        ("a", "close"), ("b", "close"),
    ]
