"""Command-line argument parsing."""

import argparse
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Args:
    """Parsed command-line arguments.

    Attributes:
        map_path: Path to the map file to simulate.
        matplotlib_window: Also show the run in a matplotlib window.
        map_arg: The map path exactly as typed, for messages; None means
            ``str(map_path)``. Not compared, so Args built by hand equal
            parsed ones.
    """

    map_path: Path
    matplotlib_window: bool = False
    map_arg: str | None = field(default=None, compare=False)

    @property
    def map_name(self) -> str:
        """Return the map path as the user typed it, for messages."""
        return str(self.map_path) if self.map_arg is None else self.map_arg


def parse_args(argv: list[str] | None = None) -> Args:
    """Parse command-line arguments into an Args instance.

    Args:
        argv: Argument list to parse, or None to use sys.argv.

    Returns:
        The parsed Args.

    Raises:
        SystemExit: On invalid arguments or ``--help`` (argparse prints
            the usage and exits with status 2, or 0 for help).
    """
    parser = argparse.ArgumentParser(prog="fly_in.py")
    parser.add_argument("map_path", metavar="MAP", help="map file")
    parser.add_argument(
        "--matplotlib-window", action="store_true",
        help="also show the run in a window (needs matplotlib)",
    )
    namespace = parser.parse_args(argv)
    return Args(
        map_path=Path(namespace.map_path),
        matplotlib_window=namespace.matplotlib_window,
        map_arg=namespace.map_path,
    )
