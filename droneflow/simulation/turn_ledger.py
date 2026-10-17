"""TurnLedger: room left in zones and connections during one turn."""

from ..pathfinding.pathfinder import Hop
from .state import SimulationState


class TurnLedger:
    """Counts the orders already given this turn, by the resolver's rules.

    The scheduler creates one ledger per turn, asks ``has_room`` before
    giving each order and calls ``record`` after giving it. The counts
    mirror ``TurnResolver``:

    * a zone's load is its occupancy plus reservations (so drones in
      flight toward a restricted zone already take room), minus drones
      ordered out of it, plus drones ordered into it; the start and end
      zones have no limit;
    * a connection's use is the drones landing through it this turn
      (``SimulationState.link_load``) plus the drones ordered across it,
      in either direction.

    Only the orders recorded so far are counted. Later orders can only add
    departures, which free more room, or entries, which are checked again,
    so every order allowed here is still legal for the whole turn.
    """

    def __init__(self, state: SimulationState) -> None:
        """Start an empty ledger over the state at the start of a turn."""
        self.state = state
        self._zone_change: dict[str, int] = {}
        self._link_use: dict[str, int] = {}

    def has_room(self, hop: Hop) -> bool:
        """Return whether one more drone can take this hop this turn.

        Both the connection and the zone entered must have room left.
        """
        connection = hop.connection
        used = self.state.link_load(connection) + self._link_use.get(
            connection.name, 0
        )
        if used >= connection.max_link_capacity:
            return False
        free = self.state.free_capacity(hop.zone.name)
        if free is None:
            return True
        return free - self._zone_change.get(hop.zone.name, 0) >= 1

    def record(self, from_zone: str, hop: Hop) -> None:
        """Count an order moving a drone from ``from_zone`` along ``hop``."""
        self._add(self._zone_change, from_zone, -1)
        self._add(self._zone_change, hop.zone.name, 1)
        self._add(self._link_use, hop.connection.name, 1)

    @staticmethod
    def _add(counts: dict[str, int], key: str, delta: int) -> None:
        counts[key] = counts.get(key, 0) + delta
