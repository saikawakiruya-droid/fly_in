"""MapValidator: turns tokenized lines into a validated World."""

from collections.abc import Sequence

from ..errors import ParseError
from ..models.connection import Connection
from ..models.network import Network
from ..models.world import World
from ..models.zone import Zone, ZoneRole
from .line_tokenizer import RawLine
from .map_format import DroneCount, Entry
from .map_rules import Rule


class MapValidator:
    """Builds the World line by line, delegating the actual checks.

    Field conversion belongs to each line's LineSpec; checks that span
    several lines belong to the Rule objects. This class only coordinates.
    """

    def __init__(self, rules: Sequence[Rule]) -> None:
        self._rules = list(rules)
        self._network = Network()
        self._nb_drones: int | None = None
        self._last_number = 0

    def accept(self, raw: RawLine) -> None:
        """Validate one tokenized line and record what it declares.

        Raises:
            droneflow.errors.ParseError: If a field is invalid or a rule is
                violated.
        """
        self._last_number = raw.number
        try:
            entry = raw.spec.build(raw.positional, raw.metadata)
            for rule in self._rules:
                rule.check(entry, self._network)
        except ValueError as error:
            raise ParseError(raw.number, str(error)) from None
        self._store(entry)

    def finish(self) -> World:
        """Check what only the whole file can show and return the World.

        Raises:
            droneflow.errors.ParseError: If the header or a required hub is
                missing.
        """
        if self._nb_drones is None:
            raise ParseError(
                self._last_number,
                "map file is empty, expected 'nb_drones: <n>' as the first "
                "line",
            )
        roles = {zone.role for zone in self._network.zones.values()}
        for role in (ZoneRole.START, ZoneRole.END):
            if role not in roles:
                raise ParseError(self._last_number, f"missing {role.value}")
        return World(network=self._network, nb_drones=self._nb_drones)

    def _store(self, entry: Entry) -> None:
        if isinstance(entry, DroneCount):
            self._nb_drones = entry.value
        elif isinstance(entry, Zone):
            self._network.add_zone(entry)
        elif isinstance(entry, Connection):
            self._network.add_connection(entry)
