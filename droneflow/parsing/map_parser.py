"""MapParser: turns a map text file into a validated World."""

from pathlib import Path

from ..models.world import World
from .line_tokenizer import LineTokenizer
from .map_format import DEFAULT_FORMAT
from .map_reader import MapReader
from .map_rules import default_rules
from .map_validator import MapValidator


class MapParser:
    """Reads and validates a Fly-in map file, producing a World.

    The work is delegated: MapReader supplies numbered lines, LineTokenizer
    splits them, and MapValidator checks and assembles the result. See the
    subject's Parser Constraints (章VII.4) for the rules being enforced.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def parse(self) -> World:
        """Parse the map file into a validated World.

        Raises:
            droneflow.errors.ParseError: If the file violates any parser
                constraint, including the offending line number and cause.
        """
        tokenizer = LineTokenizer(DEFAULT_FORMAT)
        validator = MapValidator(default_rules())
        for src in MapReader(self.path):
            if src.number == 1:
                validator.accept(tokenizer.tokenize_header(src))
                continue
            raw = tokenizer.tokenize(src)
            if raw is not None:
                validator.accept(raw)
        return validator.finish()
