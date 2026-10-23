"""Command-line argument parsing."""

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, get_args

VisualMode = Literal["terminal", "none"]
"""The accepted values of ``--visual``, as a type."""

VISUAL_MODES: tuple[str, ...] = get_args(VisualMode)
"""Accepted values of ``--visual``, in order (for argparse)."""


@dataclass(frozen=True)
class Args:
    """Parsed command-line arguments.

    Attributes:
        map_path: Path to the map file to simulate.
        visual: Visualization mode: "terminal" or "none".
        map_arg: The map path exactly as typed, for messages; None means
            ``str(map_path)``. Not compared, so Args built by hand equal
            parsed ones.
    """

    map_path: Path
    visual: VisualMode = "terminal"
    map_arg: str | None = field(default=None, compare=False)

    @property
    def map_name(self) -> str:
        """Return the map path as the user typed it, for messages."""
        return str(self.map_path) if self.map_arg is None else self.map_arg


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser of ``fly_in.py``.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(
        prog="fly_in.py",
        description=(
            "Route a fleet of drones from the start zone to the end zone "
            "in as few turns as possible. The turn log goes to standard "
            "output; the terminal view, the summary and errors go to "
            "standard error."
        ),
    )
    parser.add_argument(
        "map_path", metavar="MAP", help="map file to simulate"
    )
    parser.add_argument(
        "--visual",
        choices=VISUAL_MODES,
        default="terminal",
        help="how to show the run (default: terminal)",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> Args:
    """Parse command-line arguments into an Args instance.

    Args:
        argv: Argument list to parse, or None to use sys.argv.

    Returns:
        The parsed Args.

    Raises:
        SystemExit: On invalid arguments or ``--help`` (argparse prints
            the usage to standard error and exits with status 2, or 0
            for help).
    """
    namespace = build_parser().parse_args(argv)
    return Args(
        map_path=Path(namespace.map_path),
        visual=namespace.visual,
        map_arg=namespace.map_path,
    )
