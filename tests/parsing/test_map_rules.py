"""Tests for droneflow.parsing.map_rules."""

import pytest

from droneflow.models.connection import Connection
from droneflow.models.network import Network
from droneflow.models.zone import Zone, ZoneRole, ZoneType
from droneflow.parsing.map_rules import (
    KnownEndpoints,
    SingleStartAndEnd,
    UniqueConnection,
    UniqueZoneName,
)


def zone(name: str, role: ZoneRole = ZoneRole.HUB) -> Zone:
    """Build a minimal zone."""
    return Zone(name, 0, 0, ZoneType.NORMAL, role)


def network_with(*zones: Zone) -> Network:
    """Build a network holding the given zones."""
    network = Network()
    for z in zones:
        network.add_zone(z)
    return network


def test_unique_zone_name_rejects_a_repeated_name() -> None:
    """A second zone with an existing name is refused."""
    with pytest.raises(ValueError):
        UniqueZoneName().check(zone("a"), network_with(zone("a")))


@pytest.mark.parametrize("role", [ZoneRole.START, ZoneRole.END])
def test_single_start_and_end_rejects_a_second_one(role: ZoneRole) -> None:
    """A second start_hub or end_hub is refused; plain hubs are free."""
    network = network_with(zone("a", role))
    with pytest.raises(ValueError):
        SingleStartAndEnd().check(zone("b", role), network)
    SingleStartAndEnd().check(zone("c"), network)


def test_known_endpoints_rejects_an_undeclared_zone() -> None:
    """A connection to an unknown zone is refused."""
    network = network_with(zone("a"))
    with pytest.raises(ValueError):
        KnownEndpoints().check(Connection("a", "ghost"), network)


def test_unique_connection_treats_reversed_pair_as_duplicate() -> None:
    """a-b and b-a are the same connection."""
    network = network_with(zone("a"), zone("b"))
    network.add_connection(Connection("a", "b"))
    with pytest.raises(ValueError):
        UniqueConnection().check(Connection("b", "a"), network)


def test_unique_connection_allows_distinct_pairs_and_self_loops() -> None:
    """Different pairs and a self-loop are not duplicates."""
    network = network_with(zone("a"), zone("b"), zone("c"))
    network.add_connection(Connection("a", "b"))
    UniqueConnection().check(Connection("a", "c"), network)
    UniqueConnection().check(Connection("a", "a"), network)
