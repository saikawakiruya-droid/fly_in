"""MapParser: turns a map text file into a validated World."""

from pathlib import Path

from ..models.world import World


class MapParser:
    """Reads and validates a Fly-in map file, producing a World.

    See the subject's Parser Constraints (章VII.4) for the full validation
    rules this class must enforce.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def parse(self) -> World:
        """Parse the map file into a validated World.

        Raises:
            droneflow.errors.ParseError: If the file violates any parser
                constraint, including the offending line number and cause.
        """
        raise NotImplementedError

    def _parse_zone_line(self, line_number: int, line: str) -> None:
        """Parse a ``start_hub:`` / ``end_hub:`` / ``hub:`` line."""
        raise NotImplementedError

    def _parse_connection_line(self, line_number: int, line: str) -> None:
        """Parse a ``connection:`` line."""
        raise NotImplementedError

    def _parse_metadata(self, line_number: int, raw: str) -> dict[str, str]:
        """Parse a bracketed ``[key=value ...]`` metadata block."""
        raise NotImplementedError

    def _validate(self) -> None:
        """Run whole-file validation once every line has been read.

        Checks uniqueness of zone names, exactly one start/end zone, no
        duplicate connections, and any other cross-line constraint that
        cannot be checked line by line.
        """
        raise NotImplementedError
