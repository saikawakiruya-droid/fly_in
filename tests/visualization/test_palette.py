"""Tests for droneflow.visualization.palette (rgb), without pygame.

Color names are looked up in the package's own table, ignoring case, and
unknown names give None instead of an error (decisions 2026-10-17
"colors"). The table covers every color of the provided maps except
``rainbow``, which ``maps.tar.gz`` at the repository root shows.
"""

import re
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from droneflow.visualization import palette
from droneflow.visualization.palette import rgb

ROOT = Path(__file__).resolve().parents[2]
MAPS_ARCHIVE = ROOT / "maps.tar.gz"


def test_table_values() -> None:
    """VP01: similar reds stay distinct; every entry is a valid RGB."""
    assert rgb("red") == (220, 40, 40)
    assert rgb("darkred") == (139, 0, 0)
    assert rgb("crimson") == (220, 20, 60)
    for name, value in palette._NAMED_RGB.items():
        assert len(value) == 3, name
        assert all(isinstance(c, int) and 0 <= c <= 255 for c in value), name


@pytest.mark.parametrize("name", ["RED", "Red", "rEd"])
def test_case_is_ignored(name: str) -> None:
    """VP02: names are matched without regard to case."""
    assert rgb(name) == rgb("red")


def test_provided_map_colors(subject_map: str) -> None:
    """VP03: every color of the provided maps is known, except rainbow."""
    if not MAPS_ARCHIVE.is_file():
        pytest.fail(
            "maps.tar.gz is required at the repository root, next to "
            "tests/ (the provided maps are read from it)"
        )
    names: set[str] = set()
    with tarfile.open(MAPS_ARCHIVE, "r:gz") as archive:
        for member in archive.getmembers():
            data = archive.extractfile(member) if member.isfile() else None
            if data is not None and member.name.endswith(".txt"):
                text = data.read().decode("utf-8")
                names |= set(re.findall(r"color=(\w+)", text))

    assert len(names) == 17
    names |= set(re.findall(r"color=(\w+)", subject_map))
    assert rgb("rainbow") is None
    assert [n for n in sorted(names) if rgb(n) is None] == ["rainbow"]


@pytest.mark.parametrize("name", ["rainbow", "", None])
def test_unknown_names_give_none(name: str | None) -> None:
    """VP04 (1): unknown names, the empty name and None give None."""
    assert rgb(name) is None


def test_core_modules_do_not_import_pygame() -> None:
    """VP04 (2): the engine and the non-graphical views need no pygame."""
    code = (
        "import sys\n"
        "import droneflow.simulation.engine\n"
        "import droneflow.visualization.terminal_view\n"
        "import droneflow.simulation.observer\n"
        "import droneflow.visualization.palette\n"
        "print('pygame' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert result.stdout.strip() == "False"
