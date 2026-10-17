"""Fly-in: entry point for the drone routing simulation (42 - Fly-in)."""

import os
import sys

from droneflow.app import Application
from droneflow.cli import parse_args
from droneflow.errors import FlyInError

EXIT_INTERRUPTED = 130
"""Exit status after Ctrl+C (128 + SIGINT), as shells report it."""


def main() -> int:
    """Parse arguments, run the application, and return an exit code.

    Returns:
        0 on success, 1 if a FlyInError was raised anywhere in the
        pipeline or standard output was closed early (e.g. ``| head``),
        130 if the user pressed Ctrl+C. Invalid arguments exit with 2
        from argparse.
    """
    args = parse_args()
    try:
        Application(args).run()
    except FlyInError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED
    except BrokenPipeError:
        _silence_stdout()
        return 1
    return 0


def _silence_stdout() -> None:
    """Point stdout at devnull so the exit flush cannot fail again.

    When the reader of a pipe goes away, Python would otherwise report
    the same broken pipe once more while flushing stdout at exit.
    """
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())
    os.close(devnull)


if __name__ == "__main__":
    raise SystemExit(main())
