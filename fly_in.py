"""Fly-in: entry point for the drone routing simulation (42 - Fly-in)."""

import errno
import os
import sys

from droneflow.app import Application
from droneflow.cli import Args, parse_args
from droneflow.errors import FlyInError

EXIT_INTERRUPTED = 130
"""Exit status after Ctrl+C (128 + SIGINT), as shells report it."""


DEBUG_ENV = "FLYIN_DEBUG"
"""Set to 1 (``make debug`` does) to let unexpected exceptions propagate."""


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the application, and return an exit code.

    Args:
        argv: Arguments to parse, or None to use sys.argv.

    Returns:
        0 on success, 1 if a FlyInError was raised anywhere in the
        pipeline, standard output was closed early (e.g. ``| head``) or
        an unexpected exception occurred, 130 if the user pressed Ctrl+C.
        Invalid arguments exit with 2 from argparse.
    """
    args = parse_args(argv)
    try:
        return _run(args)
    except Exception as exc:
        # Last resort for bugs: one line instead of a traceback. With
        # FLYIN_DEBUG=1 (make debug) the exception propagates, so pdb
        # can inspect it post mortem.
        if os.environ.get(DEBUG_ENV) == "1":
            raise
        print(
            f"error: internal error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


def _run(args: Args) -> int:
    """Run the application, turning expected failures into exit codes."""
    try:
        Application(args).run()
    except FlyInError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED
    except OSError as exc:
        if not _is_closed_pipe(exc):
            raise
        _silence_stdout()
        return 1
    return 0


def _is_closed_pipe(exc: OSError) -> bool:
    """Return whether the error means the reader of stdout went away.

    That is ``BrokenPipeError`` on POSIX; Windows reports a write to a
    closed pipe as ``EINVAL`` instead. Map files that cannot be read are
    already reported as ``MapFileError``, so no other OSError is caught.
    """
    if isinstance(exc, BrokenPipeError):
        return True
    return os.name == "nt" and exc.errno == errno.EINVAL


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
