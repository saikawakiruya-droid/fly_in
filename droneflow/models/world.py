"""World: the fully parsed, ready-to-simulate map."""

from dataclasses import dataclass

from .network import Network


@dataclass
class World:
    """Bundles everything the parser produces for the rest of the pipeline.

    Attributes:
        network: The parsed zones and connections.
        nb_drones: Number of drones to route, from ``nb_drones:``.
    """

    network: Network
    nb_drones: int
