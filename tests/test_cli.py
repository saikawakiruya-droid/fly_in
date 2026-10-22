"""Tests for droneflow.cli (argument parsing, no pygame needed).

``parse_args(argv)`` is called directly. Usage errors are checked through
``SystemExit.code`` and the text argparse writes to standard error.
Decisions 2026-10-18 "the CLI's shape" and "points found by the CLI test
design" (the 60 second limit, the map path as typed).
"""

from pathlib import Path
from typing import get_args

import pytest

from droneflow.cli import (
    DEFAULT_DELAY,
    MAX_DELAY,
    VISUAL_MODES,
    Args,
    VisualMode,
    build_parser,
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
    """AC01: only MAP given: terminal view, 0.5 s, no step mode."""
    args = parse_args(["m.txt"])

    assert args == Args(
        map_path=Path("m.txt"), visual="terminal", delay=0.5, step=False
    )
    assert isinstance(args.map_path, Path)
    assert DEFAULT_DELAY == 0.5


@pytest.mark.parametrize("mode", ["terminal", "graphical", "both", "none"])
def test_visual_modes(mode: str) -> None:
    """AC02: the four --visual values, the same as VISUAL_MODES."""
    assert parse_args(["m.txt", "--visual", mode]).visual == mode
    assert VISUAL_MODES == ("terminal", "graphical", "both", "none")


@pytest.mark.parametrize("value", ["gui", "Terminal"])
def test_visual_rejects_unknown_values(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC03: unknown --visual values (case sensitive) exit with 2."""
    lines = usage_error(capsys, ["m.txt", "--visual", value])

    assert f"invalid choice: '{value}'" in lines[-1]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["m.txt", "--delay", "0"], 0.0),
        (["m.txt", "--delay", "0.25"], 0.25),
        (["m.txt", "--delay", "1e1"], 10.0),
        (["m.txt", "--delay", "-0"], 0.0),
        (["m.txt", "--delay=2"], 2.0),
    ],
    ids=["zero", "fraction", "exponent", "minus-zero", "equals-form"],
)
def test_delay_accepts(argv: list[str], expected: float) -> None:
    """AC04: finite numbers from 0 are accepted, 0 itself included."""
    delay = parse_args(argv).delay

    assert isinstance(delay, float)
    assert delay == expected


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("-1", "must be a finite number of seconds >= 0: '-1'"),
        ("-0.001", "must be a finite number of seconds >= 0: '-0.001'"),
        ("nan", "must be a finite number of seconds >= 0: 'nan'"),
        ("inf", "must be a finite number of seconds >= 0: 'inf'"),
        ("-inf", "must be a finite number of seconds >= 0: '-inf'"),
        ("abc", "not a number: 'abc'"),
        ("", "not a number: ''"),
    ],
)
def test_delay_rejects(
    value: str, reason: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC05: negative, non-finite and non-numeric delays exit with 2.

    ``-inf`` is passed as ``--delay=-inf``: written as a separate word,
    argparse takes it for an option (it is not a negative number to its
    eyes) and reports "expected one argument" instead.
    """
    argv = ["m.txt", "--delay", value]
    if value == "-inf":
        argv = ["m.txt", f"--delay={value}"]

    lines = usage_error(capsys, argv)

    assert lines[-1] == f"fly_in.py: error: argument --delay: {reason}"


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
        ["m.txt", "--visual", "none", "--step", "--delay", "3"],
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
        "--visual {terminal,graphical,both,none}",
        "--delay SECONDS",
        "--step",
        "(default: terminal)",
        f"(default: {DEFAULT_DELAY})",
        f"0 to {MAX_DELAY:g}",
    ]:
        assert text in out


def test_delay_upper_limit_is_accepted() -> None:
    """AC09: exactly 60 seconds is accepted (the boundary)."""
    assert parse_args(["m.txt", "--delay", "60"]).delay == 60.0


@pytest.mark.parametrize("value", ["60.5", "1e308"])
def test_delay_above_upper_limit(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC09: above 60 seconds is a usage error, not a later crash."""
    lines = usage_error(capsys, ["m.txt", "--delay", value])

    assert lines[-1] == (
        "fly_in.py: error: argument --delay: "
        f"must be between 0 and 60 seconds: '{value}'"
    )


def test_visual_modes_come_from_the_literal() -> None:
    """NT10: VISUAL_MODES is the Literal's values, in the same order."""
    assert VISUAL_MODES == get_args(VisualMode)
    assert VISUAL_MODES == ("terminal", "graphical", "both", "none")


def test_stage_options_default_off() -> None:
    """SC01: without the stage options nothing is written or read."""
    args = parse_args(["m.txt"])

    assert args.parse_only is None
    assert args.from_world is False
    assert args.save_run is None
    assert args == Args(Path("m.txt"))


def test_stage_paths_are_kept_as_typed() -> None:
    """SC02: the JSON paths are the strings typed, not Path objects."""
    parse_only = parse_args(["m.txt", "--parse-only", "./out/w.json"])
    from_world = parse_args(
        ["w.json", "--from-world", "--save-run", "./r.json"]
    )

    assert parse_only.parse_only == "./out/w.json"
    assert from_world.from_world is True
    assert from_world.save_run == "./r.json"


def test_parse_only_excludes_save_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SC03: --parse-only does not simulate, so --save-run is an error."""
    lines = usage_error(
        capsys, ["m.txt", "--parse-only", "w.json", "--save-run", "r.json"]
    )

    assert lines[-1] == (
        "fly_in.py: error: argument --save-run: "
        "not allowed with argument --parse-only"
    )


def test_from_world_with_parse_only() -> None:
    """SC04: a world file can be read and written again."""
    args = parse_args(["w.json", "--from-world", "--parse-only", "x.json"])

    assert args.from_world is True
    assert args.parse_only == "x.json"


def test_help_lists_the_additional_features() -> None:
    """SC05: the stage options have their own group in --help."""
    text = build_parser().format_help()

    for part in [
        "stages on their own (additional features)",
        "--parse-only FILE",
        "--from-world",
        "--save-run FILE",
    ]:
        assert part in text
