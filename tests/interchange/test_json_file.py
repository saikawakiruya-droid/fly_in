"""Tests for droneflow.interchange.json_file (JsonObject, write_json).

Every reading error is a ``ValueError`` whose message starts with where
the field is. Decision 2026-10-22 "the parser and the simulation on their
own through JSON files" 3 and 4; test design
``2026-10-22_test-design-stage-files.md`` A (JO01-JO10).
"""

import json
from pathlib import Path

import pytest

from droneflow.errors import OutputFileError
from droneflow.interchange.json_file import JsonObject, write_json
from droneflow.models.zone import ZoneType


def test_not_an_object() -> None:
    """JO01: anything but a dict is rejected, naming where it is."""
    with pytest.raises(ValueError, match=r"^top level: must be an object$"):
        JsonObject([])
    with pytest.raises(ValueError, match=r"^zones\[1\]: must be an object$"):
        JsonObject(3, "zones[1]")


def test_missing_key() -> None:
    """JO02: a missing key names its full location."""
    with pytest.raises(ValueError, match=r"^x: missing$"):
        JsonObject({}).value("x")
    with pytest.raises(ValueError, match=r"^a\.x: missing$"):
        JsonObject({}, "a").value("x")


@pytest.mark.parametrize("value", [True, 1.0, "1"])
def test_integer_rejects(value: object) -> None:
    """JO03: booleans, floats and strings are not integers."""
    with pytest.raises(ValueError, match=r"^k: must be an integer$"):
        JsonObject({"k": value}).integer("k")


def test_integer_accepts() -> None:
    """JO03: an int is returned as it is (zero and negatives included)."""
    assert JsonObject({"k": 5}).integer("k") == 5
    assert JsonObject({"k": -2}).integer("k") == -2


@pytest.mark.parametrize("value", [0, -1])
def test_positive_rejects(value: int) -> None:
    """JO04: zero and negatives are not positive."""
    with pytest.raises(ValueError, match=r"^k: must be a positive integer$"):
        JsonObject({"k": value}).positive("k")


def test_positive_accepts() -> None:
    """JO04: 1 is the smallest positive integer."""
    assert JsonObject({"k": 1}).positive("k") == 1


def test_optional_values() -> None:
    """JO05: null gives None; a value is checked like the plain accessor."""
    data = JsonObject({"n": None, "t": None, "p": 3, "s": "x", "z": 0})
    assert data.optional_positive("n") is None
    assert data.optional_text("t") is None
    assert data.optional_positive("p") == 3
    assert data.optional_text("s") == "x"
    with pytest.raises(ValueError, match=r"^z: must be a positive integer$"):
        data.optional_positive("z")
    with pytest.raises(ValueError, match=r"^q: missing$"):
        data.optional_positive("q")


def test_text() -> None:
    """JO06: only strings are text."""
    assert JsonObject({"k": "a"}).text("k") == "a"
    with pytest.raises(ValueError, match=r"^k: must be a string$"):
        JsonObject({"k": 3}).text("k")


def test_member() -> None:
    """JO07: an enum member by its value; others list the allowed ones."""
    data = JsonObject({"ok": "priority", "bad": "lava", "num": 3}, "z")
    assert data.member("ok", ZoneType) is ZoneType.PRIORITY
    with pytest.raises(ValueError) as info:
        data.member("bad", ZoneType)
    assert str(info.value) == (
        "z.bad: must be one of normal, blocked, restricted, priority, "
        "got 'lava'"
    )
    with pytest.raises(ValueError, match=r"^z\.num: must be a string$"):
        data.member("num", ZoneType)


def test_objects() -> None:
    """JO08: a list of objects, each knowing its index."""
    with pytest.raises(ValueError, match=r"^zones: must be a list$"):
        JsonObject({"zones": {}}).objects("zones")
    with pytest.raises(ValueError, match=r"^zones\[1\]: must be an object$"):
        JsonObject({"zones": [{}, 1]}).objects("zones")
    items = JsonObject({"zones": [{"name": "a"}, {}]}).objects("zones")
    assert [item.where("name") for item in items] == [
        "zones[0].name",
        "zones[1].name",
    ]
    assert items[0].text("name") == "a"


def test_write_json(tmp_path: Path) -> None:
    """JO09: indented UTF-8 JSON ending with a newline, non-ASCII kept."""
    path = tmp_path / "x.json"
    data = {"a": [1], "名前": "é"}

    write_json(str(path), data)

    text = path.read_text(encoding="utf-8")
    assert json.loads(text) == data
    assert text == json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    assert "名前" in text and "\\u" not in text


def test_write_json_failure(tmp_path: Path) -> None:
    """JO10: an unwritable path is an OutputFileError, path as given."""
    path = str(tmp_path / "no_dir" / "x.json")

    with pytest.raises(OutputFileError) as info:
        write_json(path, {})

    assert info.value.path == path
    assert info.value.reason == "No such file or directory"
    assert str(info.value) == (
        f"cannot write '{path}': No such file or directory"
    )
    assert isinstance(info.value.__cause__, OSError)
