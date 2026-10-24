"""Tests for droneflow.cli (argument parsing).

``parse_args(argv)`` is called directly. Usage errors are checked through
``SystemExit.code`` and the text argparse writes to standard error.
Decisions 2026-10-18 "the CLI's shape" and "points found by the CLI test
design" (the map path as typed).
"""

from pathlib import Path

import pytest

from droneflow.cli import Args, parse_args


def test_map_only() -> None:
    """AC01: MAP alone, kept as a Path and as typed; no window."""
    args = parse_args(["./m.txt"])

    assert args == Args(map_path=Path("m.txt"))
    assert isinstance(args.map_path, Path)
    assert args.map_name == "./m.txt"
    assert args.matplotlib_window is False


@pytest.mark.parametrize(
    "argv",
    [["--matplotlib-window", "m.txt"], ["m.txt", "--matplotlib-window"]],
    ids=["before", "after"],
)
def test_matplotlib_window_flag(argv: list[str]) -> None:
    """AC02: --matplotlib-window, before or after MAP, asks for the window."""
    assert parse_args(argv) == Args(
        map_path=Path("m.txt"), matplotlib_window=True
    )


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "the following arguments are required: MAP"),
        (["m.txt", "--visual"], "unrecognized arguments: --visual"),
        (["m.txt", "extra.txt"], "unrecognized arguments: extra.txt"),
    ],
    ids=["no-map", "unknown-option", "extra-map"],
)
def test_missing_and_unknown_arguments(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC06: a missing MAP, an option or a second MAP exit with 2."""
    with pytest.raises(SystemExit) as info:
        parse_args(argv)

    assert info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage: fly_in.py" in captured.err
    assert captured.err.splitlines()[-1] == f"fly_in.py: error: {message}"
