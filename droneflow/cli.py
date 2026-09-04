"""Command-line argument parsing."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Args:
    """Parsed command-line arguments.

    Attributes:
        map_path: Path to the map file to simulate.
        visual: Visualization mode: "terminal", "graphical", "both", or
            "none".
        debug: Whether to run the application under pdb.
    """

    map_path: Path
    visual: str
    debug: bool


def parse_args(argv: list[str] | None = None) -> Args:
    """Parse command-line arguments into an Args instance.

    Args:
        argv: Argument list to parse, or None to use sys.argv.

    Returns:
        The parsed Args.
    """
    raise NotImplementedError
