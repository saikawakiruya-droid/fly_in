"""Tests for droneflow.errors."""

from droneflow.errors import (
    FlyInError,
    ParseError,
    SimulationError,
    UnreachableGoalError,
    ZoneNotFoundError,
)


def test_zone_not_found_error_is_a_fly_in_error() -> None:
    """ZoneNotFoundError joins the project's common exception hierarchy."""
    error = ZoneNotFoundError("missing")
    assert isinstance(error, FlyInError)


def test_zone_not_found_error_keeps_the_looked_up_name() -> None:
    """The offending zone name is available on the exception."""
    error = ZoneNotFoundError("missing")
    assert error.zone_name == "missing"
    assert "missing" in str(error)


def test_unreachable_goal_error_is_its_own_fly_in_error() -> None:
    """R01: catchable as FlyInError, distinct from parse/simulation errors."""
    error = UnreachableGoalError("s", "g")
    assert isinstance(error, FlyInError)
    assert not isinstance(error, ParseError)
    assert not isinstance(error, SimulationError)


def test_unreachable_goal_error_keeps_both_zone_names() -> None:
    """R02: both names are kept and the message has no line number."""
    error = UnreachableGoalError("s", "g")
    assert error.zone_name == "s"
    assert error.goal_name == "g"
    message = str(error)
    assert "'s'" in message
    assert "'g'" in message
    assert "line" not in message
