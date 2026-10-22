"""Command-line argument parsing."""

import argparse
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, get_args

VisualMode = Literal["terminal", "graphical", "both", "none"]
"""The accepted values of ``--visual``, as a type."""

VISUAL_MODES: tuple[str, ...] = get_args(VisualMode)
"""Accepted values of ``--visual``, in order (for argparse)."""

DEFAULT_DELAY = 0.5
"""Default seconds per turn in the graphical view."""

MAX_DELAY = 60.0
"""Largest accepted ``--delay`` in seconds."""


@dataclass(frozen=True)
class Args:
    """Parsed command-line arguments.

    Attributes:
        map_path: Path to the map file to simulate.
        visual: Visualization mode: "terminal", "graphical", "both", or
            "none".
        delay: Seconds each turn stays on screen in the graphical view.
        step: Advance one turn at a time (Enter in the terminal view, the
            right arrow in the graphical view).
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
    delay: float = DEFAULT_DELAY
    step: bool = False
    map_arg: str | None = field(default=None, compare=False)
    parse_only: str | None = None
    from_world: bool = False
    save_run: str | None = None
    # LIVE CODING (--capacity-info) 1/5: add the flag's field here.

    @property
    def map_name(self) -> str:
        """Return the map path as the user typed it, for messages."""
        return str(self.map_path) if self.map_arg is None else self.map_arg


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser of ``fly_in.py``."""
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
        "--delay",
        type=_delay,
        default=DEFAULT_DELAY,
        metavar="SECONDS",
        help=(
            f"seconds per turn in the graphical view, 0 to {MAX_DELAY:g} "
            f"(default: {DEFAULT_DELAY})"
        ),
    )
    parser.add_argument(
        "--step",
        action="store_true",
        help=(
            "advance one turn at a time: Enter in the terminal view, the "
            "right arrow in the graphical view (with 'both', the window "
            "drives the steps)"
        ),
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
    # LIVE CODING (--capacity-info) 2/5: add the option here.
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
        delay=namespace.delay,
        step=namespace.step,
        map_arg=namespace.map_path,
        parse_only=namespace.parse_only,
        from_world=namespace.from_world,
        save_run=namespace.save_run,
        # LIVE CODING (--capacity-info) 3/5: pass the flag on here.
    )


def _delay(text: str) -> float:
    """Convert a ``--delay`` value, accepting 0 to MAX_DELAY seconds."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"not a number: {text!r}"
        ) from None
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError(
            f"must be a finite number of seconds >= 0: {text!r}"
        )
    if value > MAX_DELAY:
        raise argparse.ArgumentTypeError(
            f"must be between 0 and {MAX_DELAY:g} seconds: {text!r}"
        )
    return value
