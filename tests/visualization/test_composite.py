"""Tests for droneflow.visualization.composite (CompositeVisualizer).

The composite forwards each call to its views in order (``--visual=both``)
and closes every view even when closing one fails; with several failures
the last is raised and the earlier ones are chained as ``__context__``
(decisions 2026-10-17 "Stage 7 API", bugs.md 2026-10-18).
"""

from typing import Callable

import pytest

from droneflow.models.network import Network
from droneflow.simulation.state import Move, SimulationState
from droneflow.visualization.composite import CompositeVisualizer

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
    """VC01: each call goes to every view, in the views' order."""
    log: list[Entry] = []
    a, b = LogView("a", log), LogView("b", log)
    moves = [Move(1, "a")]
    composite = CompositeVisualizer([a, b])

    composite.begin(state)
    composite.render(state, moves)
    composite.close()

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
    """VC02: the failure is raised after every view is closed."""
    log: list[Entry] = []
    composite = CompositeVisualizer(
        [LogView("a", log, fail="close"), LogView("b", log)]
    )

    with pytest.raises(RuntimeError, match="^a$"):
        composite.close()
    assert log == [("a", "close"), ("b", "close")]


def test_several_failing_closes_are_chained() -> None:
    """VC03: the last failure is raised, the earlier ones as context."""
    log: list[Entry] = []
    composite = CompositeVisualizer(
        [LogView(name, log, fail="close") for name in "abc"]
    )

    with pytest.raises(RuntimeError, match="^c$") as excinfo:
        composite.close()
    assert log == [("a", "close"), ("b", "close"), ("c", "close")]
    context_b = excinfo.value.__context__
    assert isinstance(context_b, RuntimeError)
    assert str(context_b) == "b"
    context_a = context_b.__context__
    assert isinstance(context_a, RuntimeError)
    assert str(context_a) == "a"
    assert context_a.__context__ is None


def test_no_views(state: SimulationState) -> None:
    """VC04: with no views every call does nothing."""
    composite = CompositeVisualizer([])

    composite.begin(state)
    composite.render(state, [Move(1, "a")])
    composite.close()


def test_failing_render_propagates(state: SimulationState) -> None:
    """VC05: a render failure stops the round; close still closes all."""
    log: list[Entry] = []
    composite = CompositeVisualizer(
        [LogView("a", log, fail="render"), LogView("b", log)]
    )

    with pytest.raises(RuntimeError, match="^a$"):
        composite.render(state, [Move(1, "a")])
    assert log == [("a", "render")]

    composite.close()
    assert log == [("a", "render"), ("a", "close"), ("b", "close")]
