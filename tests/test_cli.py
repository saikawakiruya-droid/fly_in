"""Tests for droneflow.cli (argument parsing).

``parse_args(argv)`` is called directly. Usage errors are checked through
``SystemExit.code`` and the text argparse writes to standard error.
Decisions 2026-10-18 "the CLI's shape" and "points found by the CLI test
design" (the map path as typed).
"""

from pathlib import Path
from typing import get_args

import pytest

from droneflow.cli import (
    VISUAL_MODES,
    Args,
    VisualMode,
    parse_args,
)


def usage_error(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> list[str]:
    """Parse ``argv`` expecting exit status 2; return the stderr lines."""
    with pytest.raises(SystemExit) as info:
        parse_args(argv)
    assert info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage: fly_in.py" in captured.err
    return captured.err.splitlines()


def test_defaults() -> None:
    """AC01: only MAP given: terminal view, no step mode."""
    args = parse_args(["m.txt"])

    assert args == Args(map_path=Path("m.txt"), visual="terminal", step=False)
    assert isinstance(args.map_path, Path)


@pytest.mark.parametrize("mode", ["terminal", "none"])
def test_visual_modes(mode: str) -> None:
    """AC02: the two --visual values, the same as VISUAL_MODES."""
    assert parse_args(["m.txt", "--visual", mode]).visual == mode
    assert VISUAL_MODES == ("terminal", "none")


@pytest.mark.parametrize("value", ["graphical", "Terminal"])
def test_visual_rejects_unknown_values(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC03: unknown --visual values (case sensitive) exit with 2."""
    lines = usage_error(capsys, ["m.txt", "--visual", value])

    assert f"invalid choice: '{value}'" in lines[-1]


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "the following arguments are required: MAP"),
        (["m.txt", "--debug"], "unrecognized arguments: --debug"),
        (["m.txt", "extra.txt"], "unrecognized arguments: extra.txt"),
    ],
    ids=["no-map", "removed-debug", "extra-map"],
)
def test_missing_and_unknown_arguments(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC06: a missing MAP, --debug or a second MAP exit with 2."""
    lines = usage_error(capsys, argv)

    assert lines[-1] == f"fly_in.py: error: {message}"


@pytest.mark.parametrize(
    "argv",
    [
        ["m.txt", "--step"],
        ["m.txt", "--visual", "none", "--step"],
    ],
    ids=["default-view", "unrelated-mode"],
)
def test_step(argv: list[str]) -> None:
    """AC07: --step is accepted, even with modes that ignore it."""
    assert parse_args(argv).step is True


def test_help(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC08: --help prints to stdout, exits 0, and shows the defaults."""
    monkeypatch.setenv("COLUMNS", "200")

    with pytest.raises(SystemExit) as info:
        parse_args(["--help"])

    assert info.value.code == 0
    out = capsys.readouterr().out
    for text in [
        "usage: fly_in.py",
        "--visual {terminal,none}",
        "--step",
        "(default: terminal)",
    ]:
        assert text in out


def test_visual_modes_come_from_the_literal() -> None:
    """NT10: VISUAL_MODES is the Literal's values, in the same order."""
    assert VISUAL_MODES == get_args(VisualMode)
    assert VISUAL_MODES == ("terminal", "none")
