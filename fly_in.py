"""Fly-in: entry point for the drone routing simulation (42 - Fly-in)."""

import sys

from droneflow.app import Application
from droneflow.cli import parse_args
from droneflow.errors import FlyInError


def main() -> int:
    """Parse arguments, run the application, and return an exit code.

    Returns:
        0 on success, 1 if a FlyInError was raised anywhere in the pipeline.
    """
    args = parse_args()
    try:
        Application(args).run()
    except FlyInError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
