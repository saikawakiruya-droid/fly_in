"""Fly-in: entry point for the drone routing simulation (42 - Fly-in)."""

import sys

from droneflow.app import Application
from droneflow.cli import parse_args
from droneflow.errors import FlyInError

EXIT_INTERRUPTED = 130
"""Exit status after Ctrl+C (128 + SIGINT), as shells report it."""


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the application, and return an exit code.

    Args:
        argv: Arguments to parse, or None to use sys.argv.

    Returns:
        0 on success, 1 if a FlyInError or an unexpected exception was
        raised, 130 if the user pressed Ctrl+C. Invalid arguments exit
        with 2 from argparse.
    """
    args = parse_args(argv)
    try:
        Application(args).run()
    except FlyInError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED
    except Exception as exc:
        # Last resort for bugs: one line instead of a traceback.
        print(
            f"error: internal error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
