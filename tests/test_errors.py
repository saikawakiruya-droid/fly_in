"""Tests for droneflow.errors."""

from droneflow.errors import FlyInError, ZoneNotFoundError


def test_zone_not_found_error_is_a_fly_in_error() -> None:
    """ZoneNotFoundError joins the project's common exception hierarchy."""
    error = ZoneNotFoundError("missing")
    assert isinstance(error, FlyInError)


def test_zone_not_found_error_keeps_the_looked_up_name() -> None:
    """The offending zone name is available on the exception."""
    error = ZoneNotFoundError("missing")
    assert error.zone_name == "missing"
    assert "missing" in str(error)
