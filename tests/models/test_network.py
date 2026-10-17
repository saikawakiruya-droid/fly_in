"""Tests for droneflow.models.network."""

import pytest

from droneflow.errors import SimulationError, ZoneNotFoundError
from droneflow.models.connection import Connection
from droneflow.models.network import Network
from droneflow.models.zone import Zone, ZoneRole, ZoneType


def make_zone(name: str, role: ZoneRole = ZoneRole.HUB) -> Zone:
    """Build a minimal NORMAL zone for use as test fixture data."""
    return Zone(name=name, x=0, y=0, zone_type=ZoneType.NORMAL, role=role)


def test_add_and_get_zone() -> None:
    """A registered zone can be looked up by name."""
    network = Network()
    zone = make_zone("a")
    network.add_zone(zone)
    assert network.get_zone("a") is zone


def test_get_zone_raises_for_unknown_name() -> None:
    """Looking up a name that was never registered fails clearly."""
    network = Network()
    with pytest.raises(ZoneNotFoundError) as excinfo:
        network.get_zone("missing")
    assert excinfo.value.zone_name == "missing"


def test_add_connection_updates_adjacency_for_both_ends() -> None:
    """Registering a connection makes it visible from either endpoint."""
    network = Network()
    network.add_zone(make_zone("a"))
    network.add_zone(make_zone("b"))
    connection = Connection(zone_a="a", zone_b="b")
    network.add_connection(connection)

    assert network.neighbors("a") == [connection]
    assert network.neighbors("b") == [connection]


def test_neighbors_empty_for_zone_with_no_connections() -> None:
    """A zone with no registered connections has an empty neighbor list."""
    network = Network()
    network.add_zone(make_zone("a"))
    assert network.neighbors("a") == []


def test_neighbors_empty_for_unknown_zone() -> None:
    """Asking for neighbors of an unregistered zone name is not an error."""
    network = Network()
    assert network.neighbors("missing") == []


def test_start_zone_and_end_zone() -> None:
    """start_zone and end_zone return the uniquely-roled zones."""
    network = Network()
    start = make_zone("start", role=ZoneRole.START)
    end = make_zone("end", role=ZoneRole.END)
    network.add_zone(start)
    network.add_zone(end)
    network.add_zone(make_zone("hub"))

    assert network.start_zone is start
    assert network.end_zone is end


def test_start_zone_raises_when_absent() -> None:
    """No START-role zone registered is an invariant violation."""
    network = Network()
    network.add_zone(make_zone("hub"))
    with pytest.raises(SimulationError):
        network.start_zone


def test_start_zone_raises_when_duplicated() -> None:
    """More than one START-role zone is an invariant violation."""
    network = Network()
    network.add_zone(make_zone("start1", role=ZoneRole.START))
    network.add_zone(make_zone("start2", role=ZoneRole.START))
    with pytest.raises(SimulationError):
        network.start_zone


def test_end_zone_raises_when_absent() -> None:
    """No END-role zone registered is an invariant violation."""
    network = Network()
    network.add_zone(make_zone("hub"))
    with pytest.raises(SimulationError):
        network.end_zone


def network_with(names: str, *edges: tuple[str, str]) -> Network:
    """Build a network of NORMAL hubs and the given connections."""
    network = Network()
    for name in names:
        network.add_zone(make_zone(name))
    for zone_a, zone_b in edges:
        network.add_connection(Connection(zone_a=zone_a, zone_b=zone_b))
    return network


def test_connection_between_works_in_both_directions() -> None:
    """M02: the lookup ignores direction and returns the same object."""
    network = network_with("ab", ("a", "b"))
    connection = network.connections[0]

    assert network.connection_between("a", "b") is connection
    assert network.connection_between("b", "a") is connection


def test_connection_between_returns_none_when_not_linked() -> None:
    """M03: unlinked or unknown zones give None, not an exception."""
    network = network_with("abc", ("a", "b"))

    assert network.connection_between("a", "c") is None
    assert network.connection_between("nope", "a") is None


@pytest.mark.parametrize("has_loop", [True, False])
def test_connection_between_finds_self_loop(has_loop: bool) -> None:
    """M04: passing the same zone twice finds a declared self-loop."""
    edges = [("a", "a"), ("a", "b")] if has_loop else [("a", "b")]
    network = network_with("ab", *edges)

    found = network.connection_between("a", "a")
    if has_loop:
        assert found is network.connections[0]
    else:
        assert found is None
