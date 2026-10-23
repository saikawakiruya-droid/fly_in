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
        step: Advance one turn at a time (Enter in the terminal view).
        map_arg: The map path exactly as typed, for messages; None means
            ``str(map_path)``. Not compared, so Args built by hand equal
            parsed ones.
        parse_only: Write the parsed World to this JSON file and stop,
            without simulating (``--parse-only``); None to simulate.
        from_world: Read ``map_path`` as a world JSON file written by
            ``--parse-only`` instead of parsing a map (``--from-world``).
        save_run: Write every turn's moves and state to this JSON file
            (``--save-run``); None to write none.
    """

    map_path: Path
    visual: VisualMode = "terminal"
    step: bool = False
    map_arg: str | None = field(default=None, compare=False)
    parse_only: str | None = None
    from_world: bool = False
    save_run: str | None = None

    @property
    def map_name(self) -> str:
        """Return the map path as the user typed it, for messages."""
        return str(self.map_path) if self.map_arg is None else self.map_arg


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser of ``fly_in.py``.

    Returns:
        The parser, with the options of the subject and the additional
        features.
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
    parser.add_argument(
        "--step",
        action="store_true",
        help="advance one turn at a time (Enter in the terminal view)",
    )
    extra = parser.add_argument_group(
        "stages on their own (additional features)",
        "Run the parser or the simulation alone; what one hands to the "
        "next goes through a JSON file you can read.",
    )
    extra.add_argument(
        "--from-world",
        action="store_true",
        help=(
            "MAP is a world JSON file written by --parse-only: simulate "
            "it without the parser"
        ),
    )
    outputs = extra.add_mutually_exclusive_group()
    outputs.add_argument(
        "--parse-only",
        metavar="FILE",
        help="parse MAP, write the World to FILE as JSON, and stop",
    )
    outputs.add_argument(
        "--save-run",
        metavar="FILE",
        help=(
            "write every turn's moves and the state after it to FILE as "
            "JSON"
        ),
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
        step=namespace.step,
        map_arg=namespace.map_path,
        parse_only=namespace.parse_only,
        from_world=namespace.from_world,
        save_run=namespace.save_run,
    )
