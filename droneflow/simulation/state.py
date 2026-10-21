"""SimulationState: the mutable per-turn state of the whole simulation."""

from dataclasses import dataclass

from ..errors import SimulationError
from ..models.connection import Connection
from ..models.drone import Drone, DroneStatus
from ..models.network import Network
from ..models.zone import ZoneRole


@dataclass(frozen=True)
class Move:
    """One drone's action during a single turn, as printed in the output.

    Moves are produced by the ``TurnResolver`` (driven by the engine),
    never by the scheduler.

    Attributes:
        drone_id: Which drone moved.
        destination: Target zone name, or the connection name if the drone
            just entered a restricted-zone transit.
        connection: Name of the connection the drone departed along, or
            None for a landing (the drone left its connection then). Only
            departures count toward a connection's capacity.
    """

    drone_id: int
    destination: str
    connection: str | None = None

    @property
    def text(self) -> str:
        """Return the move as printed: ``D<id>-<destination>``."""
        return f"D{self.drone_id}-{self.destination}"


@dataclass(frozen=True)
class MoveOrder:
    """A scheduler's instruction: move one drone into an adjacent zone.

    The scheduler always names the zone to enter, even a restricted one;
    the ``TurnResolver`` turns that into the connection-name output and
    lands the drone on the next turn by itself.

    Attributes:
        drone_id: Which drone to move.
        zone: Name of the adjacent zone the drone should enter.
    """

    drone_id: int
    zone: str


class SimulationState:
    """Where every drone is, and how full every zone is, between turns.

    ``load`` counts the drones currently in a zone plus the drones in
    flight toward it (``reserved``), which is what the views display. The
    rules count a drone in flight in its zone only from the turn it lands;
    the scheduler makes sure it will have room then (see ``Scheduler``).

    The mutating methods (``enter_zone``, ``enter_transit``,
    ``complete_transit``) apply one move without checking any rule; the
    ``TurnResolver`` checks a whole turn before calling them.

    Attributes:
        network: The map being simulated (read only).
        turn_number: Number of turns played so far (0 before the first).
        drones: Every drone, delivered or not, keyed by drone_id (1-based).
    """

    def __init__(self, network: Network, nb_drones: int) -> None:
        """Place ``nb_drones`` drones, numbered from 1, in the start zone."""
        self.network = network
        self.turn_number = 0
        start = network.start_zone.name
        self.drones: dict[int, Drone] = {
            drone_id: Drone(drone_id=drone_id, current_zone=start)
            for drone_id in range(1, nb_drones + 1)
        }
        self._occupancy: dict[str, int] = {start: nb_drones}
        self._reserved: dict[str, int] = {}
        self._link_load: dict[str, int] = {}

    def occupancy(self, zone_name: str) -> int:
        """Return how many undelivered drones are currently in the zone."""
        return self._occupancy.get(zone_name, 0)

    def reserved(self, zone_name: str) -> int:
        """Return how many drones in flight will arrive in the zone."""
        return self._reserved.get(zone_name, 0)

    def load(self, zone_name: str) -> int:
        """Return occupancy plus reservations: the room already taken."""
        return self.occupancy(zone_name) + self.reserved(zone_name)

    def link_load(self, connection: Connection) -> int:
        """Return how many drones are in flight on the connection.

        These drones land at the start of the next turn and leave the
        connection then, so they do not take any of its
        ``max_link_capacity`` during that turn: a connection is used only
        on the turn a drone departs across it.
        """
        return self._link_load.get(connection.name, 0)

    def active_drones(self) -> list[Drone]:
        """Return the undelivered drones, in drone_id order."""
        return [d for d in self.drones.values() if not d.is_delivered]

    def drones_in_transit(self) -> list[Drone]:
        """Return the drones in flight toward a restricted zone."""
        return [
            d for d in self.drones.values()
            if d.status is DroneStatus.IN_TRANSIT
        ]

    def drones_at(self, zone_name: str) -> list[Drone]:
        """Return the undelivered drones currently in the zone."""
        return [
            d for d in self.active_drones() if d.current_zone == zone_name
        ]

    @property
    def delivered_count(self) -> int:
        """Return how many drones have reached the end zone."""
        return sum(1 for d in self.drones.values() if d.is_delivered)

    @property
    def is_complete(self) -> bool:
        """Return whether every drone has reached the end zone."""
        return all(d.is_delivered for d in self.drones.values())

    def enter_zone(self, drone_id: int, zone_name: str) -> None:
        """Move a drone standing in a zone straight into another zone.

        Entering the end zone delivers the drone.
        """
        drone = self._drone_at_zone(drone_id)
        self._leave(drone)
        self._arrive(drone, zone_name)

    def enter_transit(
        self, drone_id: int, connection: Connection, zone_name: str
    ) -> None:
        """Start a two-turn move: the drone leaves its zone for a connection.

        The drone counts in ``reserved(zone_name)`` until it lands on the
        next turn.
        """
        drone = self._drone_at_zone(drone_id)
        self._leave(drone)
        drone.status = DroneStatus.IN_TRANSIT
        drone.in_transit_connection = connection.name
        drone.transit_target = zone_name
        self._add(self._reserved, zone_name, 1)
        self._add(self._link_load, connection.name, 1)

    def complete_transit(self, drone_id: int) -> None:
        """Land a drone in flight in the zone it was flying to."""
        drone = self.drones[drone_id]
        target = drone.transit_target
        link = drone.in_transit_connection
        if drone.status is not DroneStatus.IN_TRANSIT or target is None:
            raise SimulationError(f"drone D{drone_id} is not in flight")
        self._add(self._reserved, target, -1)
        if link is not None:
            self._add(self._link_load, link, -1)
        drone.in_transit_connection = None
        drone.transit_target = None
        self._arrive(drone, target)

    def _drone_at_zone(self, drone_id: int) -> Drone:
        drone = self.drones[drone_id]
        if drone.status is not DroneStatus.AT_ZONE:
            raise SimulationError(f"drone D{drone_id} is not in a zone")
        return drone

    def _leave(self, drone: Drone) -> None:
        if drone.current_zone is not None:
            self._add(self._occupancy, drone.current_zone, -1)
        drone.current_zone = None

    def _arrive(self, drone: Drone, zone_name: str) -> None:
        drone.current_zone = zone_name
        if self.network.get_zone(zone_name).role is ZoneRole.END:
            drone.status = DroneStatus.DELIVERED
            return
        drone.status = DroneStatus.AT_ZONE
        self._add(self._occupancy, zone_name, 1)

    @staticmethod
    def _add(counts: dict[str, int], key: str, delta: int) -> None:
        value = counts.get(key, 0) + delta
        if value:
            counts[key] = value
        else:
            counts.pop(key, None)
