"""Tests for droneflow.models.drone."""

import pytest

from droneflow.models.drone import Drone, DroneStatus


def test_is_delivered_true_when_status_is_delivered() -> None:
    """A drone that reached DELIVERED status is delivered."""
    drone = Drone(drone_id=1, current_zone="end", status=DroneStatus.DELIVERED)
    assert drone.is_delivered is True


@pytest.mark.parametrize(
    "status",
    [DroneStatus.AT_ZONE],
)
def test_is_delivered_false_for_other_statuses(status: DroneStatus) -> None:
    """A drone that has not reached DELIVERED status is not delivered."""
    drone = Drone(drone_id=1, current_zone="a", status=status)
    assert drone.is_delivered is False


def test_is_delivered_false_while_in_transit() -> None:
    """A drone mid-transit through a restricted connection is not delivered."""
    drone = Drone(
        drone_id=1,
        current_zone=None,
        status=DroneStatus.IN_TRANSIT,
        in_transit_connection="a-b",
    )
    assert drone.is_delivered is False


def test_transit_target_defaults_to_none() -> None:
    """M05: a drone standing in a zone has no transit target."""
    assert Drone(drone_id=1, current_zone="s").transit_target is None


def test_transit_target_kept_while_in_transit() -> None:
    """M05: a drone in flight keeps the zone it will land in."""
    drone = Drone(
        drone_id=1,
        current_zone=None,
        status=DroneStatus.IN_TRANSIT,
        in_transit_connection="s-r",
        transit_target="r",
    )
    assert drone.transit_target == "r"
