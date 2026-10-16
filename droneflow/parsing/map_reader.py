"""MapReader: yields the lines of a map file together with line numbers."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceLine:
    """One line of the map file.

    Attributes:
        number: 1-based line number, used in every ParseError.
        text: The line content, without the trailing newline.
    """

    number: int
    text: str


class MapReader:
    """Reads a map file and yields its lines as SourceLine objects."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def __iter__(self) -> Iterator[SourceLine]:
        with open(self.path, encoding="utf-8") as f:
            for number, text in enumerate(f, start=1):
                yield SourceLine(number, text.rstrip("\r\n"))
