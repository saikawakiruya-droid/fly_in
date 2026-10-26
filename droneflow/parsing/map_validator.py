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
    """Turns tokenized lines, checked one by one, into a validated World.

    Field conversion belongs to each line's LineSpec; checks that span
    several lines belong to the Rule objects. This class only coordinates.
    """

    def __init__(self, rules: Sequence[Rule]) -> None:
        """Start an empty network checked by ``rules``.

        Args:
            rules: The checks applied to every entry, in order.
        """
        self._rules = list(rules)
        self._network = Network()
        self._nb_drones: int | None = None
        self._last_number = 0

    def accept(self, raw: RawLine) -> None:
        """Validate one tokenized line and record what it declares.

        Args:
            raw: The tokenized line.

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

        Returns:
            The network built so far and the declared drone count.

        Raises:
            droneflow.errors.ParseError: If the header or a required hub is
                missing.
        """
        if self._nb_drones is None:
            # Line 1 is always read as the header (anything else there is
            # already an error), so no header means the file has no line:
            # report line 1, where 'nb_drones:' was expected.
            raise ParseError(
                1,
                "map file is empty, expected 'nb_drones: <n>' as the first "
                "line",
            )
        roles = {zone.role for zone in self._network.zones.values()}
        for role in (ZoneRole.START, ZoneRole.END):
            if role not in roles:
                raise ParseError(self._last_number, f"missing {role.value}")
        return World(network=self._network, nb_drones=self._nb_drones)

    def _store(self, entry: Entry) -> None:
        """Record a checked entry: the drone count, a zone or a connection.

        Args:
            entry: The entry built from one line.
        """
        if isinstance(entry, DroneCount):
            self._nb_drones = entry.value
        elif isinstance(entry, Zone):
            self._network.add_zone(entry)
        elif isinstance(entry, Connection):
            self._network.add_connection(entry)
