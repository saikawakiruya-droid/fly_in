"""MapParser: turns a map text file into a validated World."""

from pathlib import Path

from map_parser_format import DEFAULT_FORMAT
from map_parser_reader import MapReader
from map_parser_rules import default_rules
from map_parser_tokenizer import LineTokenizer
from map_parser_validator import MapValidator
from world import World


class MapParser:
    """Reads and validates a Fly-in map file, producing a World.

    The work is delegated: MapReader supplies numbered lines, LineTokenizer
    splits them, and MapValidator checks and assembles the result. See the
    subject's Parser Constraints (章VII.4) for the rules being enforced.
    """

    def __init__(self, path: str | Path) -> None:
        """Keep the path of the map file to parse.

        Args:
            path: The map file.
        """
        self.path = Path(path)

    def parse(self) -> World:
        """Parse the map file into a validated World.

        Returns:
            The network and drone count the file declares.

        Raises:
            errors.ParseError: If the file violates any parser
                constraint, including the offending line number and cause.
            OSError: If the file cannot be opened.
            UnicodeDecodeError: If the file is not UTF-8 text.
        """
        tokenizer = LineTokenizer(DEFAULT_FORMAT)
        validator = MapValidator(default_rules())
        header_read = False
        for line in MapReader(self.path):
            if tokenizer.skips(line):
                continue
            if not header_read:
                validator.accept(tokenizer.tokenize_header(line))
                header_read = True
                continue
            raw = tokenizer.tokenize(line)
            if raw is not None:
                validator.accept(raw)
        return validator.finish()
