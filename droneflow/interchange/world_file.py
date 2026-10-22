"""WorldFile: the parsed map (a World) as a JSON file, and back.

``--parse-only`` writes the World the parser built; ``--from-world`` reads
it back and runs the simulation without the parser. The file holds every
zone and connection with every field, in declaration order:

    {"format": "fly_in.world", "version": 1, "nb_drones": 5,
     "zones": [{"name": "hub", "x": 0, "y": 0, "zone_type": "normal",
                "role": "start_hub", "color": "green",
                "max_drones": null}, ...],
     "connections": [{"zone_a": "hub", "zone_b": "roof1",
                      "max_link_capacity": 1}, ...]}

Reading checks what the parser guarantees, so a file edited by hand
cannot give the simulation a map the parser would have rejected.
"""

import json
from collections.abc import Sequence
from pathlib import Path

from ..errors import WorldFileError
from ..models.connection import Connection
from ..models.network import Network
from ..models.world import World
from ..models.zone import Zone, ZoneRole, ZoneType
from ..parsing.map_format import to_zone_name
from ..parsing.map_rules import Rule, default_rules
from .json_file import JsonObject, write_json

WORLD_FORMAT = "fly_in.world"
"""The ``format`` value of a world file."""

WORLD_VERSION = 1
"""The ``version`` value of the world files this code writes and reads."""


def world_to_json(world: World) -> dict[str, object]:
    """Return the World as plain JSON values."""
    network = world.network
    return {
        "format": WORLD_FORMAT,
        "version": WORLD_VERSION,
        "nb_drones": world.nb_drones,
        "zones": [
            {
                "name": zone.name,
                "x": zone.x,
                "y": zone.y,
                "zone_type": zone.zone_type.value,
                "role": zone.role.value,
                "color": zone.color,
                "max_drones": zone.max_drones,
            }
            for zone in network.zones.values()
        ],
        "connections": [
            {
                "zone_a": connection.zone_a,
                "zone_b": connection.zone_b,
                "max_link_capacity": connection.max_link_capacity,
            }
            for connection in network.connections
        ],
    }


def world_from_json(data: object) -> World:
    """Rebuild the World from what ``world_to_json`` returns.

    Raises:
        ValueError: If a field is missing or invalid, or the map breaks a
            parser constraint; the message starts with where.
    """
    top = JsonObject(data)
    if top.value("format") != WORLD_FORMAT:
        raise ValueError(f"format: must be {WORLD_FORMAT!r}")
    if top.value("version") != WORLD_VERSION:
        raise ValueError(f"version: must be {WORLD_VERSION}")
    nb_drones = top.positive("nb_drones")
    rules = default_rules()
    network = Network()
    for item in top.objects("zones"):
        zone = _zone(item)
        _check(rules, zone, network, item.where("name"))
        network.add_zone(zone)
    for item in top.objects("connections"):
        connection = Connection(
            item.text("zone_a"),
            item.text("zone_b"),
            item.positive("max_link_capacity"),
        )
        _check(rules, connection, network, item.where("zone_a"))
        network.add_connection(connection)
    roles = {zone.role for zone in network.zones.values()}
    for role in (ZoneRole.START, ZoneRole.END):
        if role not in roles:
            raise ValueError(f"zones: missing {role.value}")
    return World(network=network, nb_drones=nb_drones)


def _zone(item: JsonObject) -> Zone:
    """Build one zone the way the parser would.

    Hubs need a positive ``max_drones``; start and end ignore it, as on a
    map line, and may not be blocked.
    """
    name = item.text("name")
    try:
        to_zone_name(name)
    except ValueError as error:
        raise ValueError(f"{item.where('name')}: {error}") from None
    zone_type = item.member("zone_type", ZoneType)
    role = item.member("role", ZoneRole)
    if role is ZoneRole.HUB:
        max_drones: int | None = item.positive("max_drones")
    else:
        item.optional_positive("max_drones")
        max_drones = None
        if zone_type is ZoneType.BLOCKED:
            raise ValueError(
                f"{item.where('zone_type')}: {role.value} cannot be blocked"
            )
    return Zone(
        name=name,
        x=item.integer("x"),
        y=item.integer("y"),
        zone_type=zone_type,
        role=role,
        color=item.optional_text("color"),
        max_drones=max_drones,
    )


def _check(
    rules: Sequence[Rule],
    entry: Zone | Connection,
    network: Network,
    where: str,
) -> None:
    """Apply the parser's rules to ``entry``, naming where it is."""
    for rule in rules:
        try:
            rule.check(entry, network)
        except ValueError as error:
            raise ValueError(f"{where}: {error}") from None


class WorldFile:
    """Writes a World to a JSON file, or reads one back.

    Attributes:
        path: The file to write or read.
        name: The path as the user typed it, for messages.
    """

    def __init__(self, path: str | Path, name: str | None = None) -> None:
        """Keep the file path, and how to name it in messages.

        Args:
            path: The file to write or read.
            name: The path as typed on the command line; None means
                ``str(path)``.
        """
        self.path = Path(path)
        self.name = str(path) if name is None else name

    def write(self, world: World) -> None:
        """Write the World.

        Raises:
            droneflow.errors.OutputFileError: If the file cannot be
                written.
        """
        write_json(self.path, world_to_json(world), self.name)

    def read(self) -> World:
        """Read the World back.

        Raises:
            WorldFileError: If the file is not JSON, or not a valid world.
            OSError: If the file cannot be opened.
            UnicodeDecodeError: If the file is not UTF-8 text.
        """
        with open(self.path, encoding="utf-8") as f:
            text = f.read()
        try:
            return world_from_json(json.loads(text))
        except json.JSONDecodeError as exc:
            raise WorldFileError(
                self.name, f"not JSON: {exc.msg} (line {exc.lineno})"
            ) from None
        except ValueError as exc:
            raise WorldFileError(self.name, str(exc)) from None
