"""Reading and writing the JSON files named on the command line."""

import json
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import TypeVar

from ..errors import OutputFileError

E = TypeVar("E", bound=Enum)


def write_json(
    path: str | Path, data: Mapping[str, object], name: str | None = None
) -> None:
    """Write ``data`` to ``path`` as indented UTF-8 JSON.

    Args:
        path: The file to write.
        data: Plain JSON values (dicts, lists, str, int, float, bool,
            None).
        name: The path as typed on the command line, for the error;
            None means ``str(path)``.

    Raises:
        OutputFileError: If the file cannot be written.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as exc:
        reason = exc.strerror or type(exc).__name__
        shown = str(path) if name is None else name
        raise OutputFileError(shown, reason) from exc


class JsonObject:
    """A JSON object read field by field, with typed accessors.

    Every error is a ``ValueError`` whose message starts with where the
    field is (``zones[2].max_drones: ...``), so the caller can report it
    as it is.
    """

    def __init__(self, data: object, where: str = "") -> None:
        """Wrap ``data``, found at ``where`` ("" for the top level).

        Raises:
            ValueError: If ``data`` is not a JSON object.
        """
        if not isinstance(data, dict):
            raise ValueError(f"{where or 'top level'}: must be an object")
        self._data: dict[str, object] = data
        self._where = where

    def where(self, key: str) -> str:
        """Return the location of ``key`` inside this object."""
        return f"{self._where}.{key}" if self._where else key

    def value(self, key: str) -> object:
        """Return the raw value of ``key``.

        Raises:
            ValueError: If the key is missing.
        """
        if key not in self._data:
            raise ValueError(f"{self.where(key)}: missing")
        return self._data[key]

    def integer(self, key: str) -> int:
        """Return ``key`` as an integer (``true``/``false`` are not)."""
        value = self.value(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{self.where(key)}: must be an integer")
        return value

    def positive(self, key: str) -> int:
        """Return ``key`` as an integer greater than zero."""
        value = self.integer(key)
        if value <= 0:
            raise ValueError(
                f"{self.where(key)}: must be a positive integer"
            )
        return value

    def optional_positive(self, key: str) -> int | None:
        """Return ``key`` as a positive integer, or None for ``null``."""
        if self.value(key) is None:
            return None
        return self.positive(key)

    def text(self, key: str) -> str:
        """Return ``key`` as a string."""
        value = self.value(key)
        if not isinstance(value, str):
            raise ValueError(f"{self.where(key)}: must be a string")
        return value

    def optional_text(self, key: str) -> str | None:
        """Return ``key`` as a string, or None for ``null``."""
        if self.value(key) is None:
            return None
        return self.text(key)

    def member(self, key: str, kind: type[E]) -> E:
        """Return ``key`` as the member of ``kind`` with that value."""
        value = self.text(key)
        try:
            return kind(value)
        except ValueError:
            allowed = ", ".join(str(member.value) for member in kind)
            raise ValueError(
                f"{self.where(key)}: must be one of {allowed}, "
                f"got {value!r}"
            ) from None

    def objects(self, key: str) -> list["JsonObject"]:
        """Return ``key`` as a list of objects, each knowing its index."""
        value = self.value(key)
        if not isinstance(value, list):
            raise ValueError(f"{self.where(key)}: must be a list")
        return [
            JsonObject(item, f"{self.where(key)}[{index}]")
            for index, item in enumerate(value)
        ]
