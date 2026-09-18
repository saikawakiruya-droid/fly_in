"""Tests for droneflow.models.connection."""

import pytest

from droneflow.models.connection import Connection


def test_involves_both_endpoints() -> None:
    """A connection involves both of its declared endpoints."""
    connection = Connection(zone_a="a", zone_b="b")
    assert connection.involves("a") is True
    assert connection.involves("b") is True


def test_involves_returns_false_for_unrelated_zone() -> None:
    """A connection does not involve a zone it was not built with."""
    connection = Connection(zone_a="a", zone_b="b")
    assert connection.involves("z") is False


def test_other_end_from_zone_a() -> None:
    """From zone_a, the other end is zone_b."""
    connection = Connection(zone_a="a", zone_b="b")
    assert connection.other_end("a") == "b"


def test_other_end_from_zone_b() -> None:
    """From zone_b, the other end is zone_a."""
    connection = Connection(zone_a="a", zone_b="b")
    assert connection.other_end("b") == "a"


def test_other_end_raises_for_unrelated_zone() -> None:
    """Asking for the other end of a zone not on this connection fails."""
    connection = Connection(zone_a="a", zone_b="b")
    with pytest.raises(ValueError):
        connection.other_end("z")
