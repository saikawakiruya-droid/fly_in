"""Command-line argument parsing."""

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

VISUAL_MODES = ("terminal", "graphical", "both", "none")
"""Accepted values of ``--visual``."""

DEFAULT_DELAY = 0.5
"""Default seconds per turn in the graphical view."""


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
    """

    map_path: Path
    visual: str = "terminal"
    delay: float = DEFAULT_DELAY
    step: bool = False


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
        "map_path", type=Path, metavar="MAP", help="map file to simulate"
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
            "seconds per turn in the graphical view "
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
        map_path=namespace.map_path,
        visual=namespace.visual,
        delay=namespace.delay,
        step=namespace.step,
    )


def _delay(text: str) -> float:
    """Convert a ``--delay`` value, accepting finite numbers >= 0 only."""
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
    return value
