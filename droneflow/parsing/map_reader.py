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
    """Reads a map file and yields its lines as SourceLine objects.

    The file is read as UTF-8; a byte order mark at its start, as some
    editors write, is skipped.
    """

    def __init__(self, path: str | Path) -> None:
        """Keep the path of the file to read."""
        self.path = Path(path)

    def __iter__(self) -> Iterator[SourceLine]:
        """Yield every line, numbered from 1, without its line ending.

        Raises:
            OSError: If the file cannot be opened.
            UnicodeDecodeError: If the file is not UTF-8 text.
        """
        with open(self.path, encoding="utf-8-sig") as f:
            for number, text in enumerate(f, start=1):
                yield SourceLine(number, text.rstrip("\r\n"))
