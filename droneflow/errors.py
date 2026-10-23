"""Custom exception types for the Fly-in drone routing simulation."""


class FlyInError(Exception):
    """Base class for all Fly-in specific errors."""


class ParseError(FlyInError):
    """Raised when the map file is syntactically or semantically invalid.

    Attributes:
        line_number: 1-based line number where the problem was found.
        reason: Human readable description of what went wrong.
    """

    def __init__(self, line_number: int, reason: str) -> None:
        """Build ``line <n>: <reason>``.

        Args:
            line_number: 1-based line number where the problem was found.
            reason: Human readable description of what went wrong.
        """
        self.line_number = line_number
        self.reason = reason
        super().__init__(f"line {line_number}: {reason}")


class ZoneNotFoundError(FlyInError):
    """Raised when a zone name cannot be found in the network.

    Attributes:
        zone_name: The name that was looked up and not found.
    """

    def __init__(self, zone_name: str) -> None:
        """Build ``zone not found: <name>``.

        Args:
            zone_name: The name that was looked up and not found.
        """
        self.zone_name = zone_name
        super().__init__(f"zone not found: {zone_name}")


class SimulationError(FlyInError):
    """Raised when the simulation reaches an illegal or unresolvable state."""


class UnreachableGoalError(FlyInError):
    """Raised when the end zone cannot be reached from a given zone.

    This is a property of the whole map rather than of a single line, so
    the message carries zone names instead of a line number.

    Attributes:
        zone_name: The zone the goal was looked for from (usually start).
        goal_name: The name of the end zone.
    """

    def __init__(self, zone_name: str, goal_name: str) -> None:
        """Build ``goal '<end>' is unreachable from '<zone>'``.

        Args:
            zone_name: The zone the goal was looked for from.
            goal_name: The name of the end zone.
        """
        self.zone_name = zone_name
        self.goal_name = goal_name
        super().__init__(
            f"goal {goal_name!r} is unreachable from {zone_name!r}"
        )


class MapFileError(FlyInError):
    """Raised when the map file cannot be opened or read as text.

    Attributes:
        path: The map file path as given on the command line.
        reason: Why it could not be read (e.g. "No such file or
            directory").
    """

    def __init__(self, path: str, reason: str) -> None:
        """Build ``cannot read map file '<path>': <reason>``.

        Args:
            path: The map file path as given on the command line.
            reason: Why it could not be read.
        """
        self.path = path
        self.reason = reason
        super().__init__(f"cannot read map file '{path}': {reason}")


class WorldFileError(FlyInError):
    """Raised when a world file (written by ``--parse-only``) is invalid.

    Attributes:
        path: The world file path as given on the command line.
        reason: What is wrong, starting with where in the file (e.g.
            ``zones[2].max_drones: must be a positive integer``).
    """

    def __init__(self, path: str, reason: str) -> None:
        """Build ``invalid world file '<path>': <reason>``.

        Args:
            path: The world file path as given on the command line.
            reason: What is wrong, starting with where in the file.
        """
        self.path = path
        self.reason = reason
        super().__init__(f"invalid world file '{path}': {reason}")


class OutputFileError(FlyInError):
    """Raised when a file asked for on the command line cannot be written.

    Attributes:
        path: The file path as given on the command line.
        reason: Why it could not be written (e.g. "No such file or
            directory").
    """

    def __init__(self, path: str, reason: str) -> None:
        """Build ``cannot write '<path>': <reason>``.

        Args:
            path: The file path as given on the command line.
            reason: Why it could not be written.
        """
        self.path = path
        self.reason = reason
        super().__init__(f"cannot write '{path}': {reason}")
