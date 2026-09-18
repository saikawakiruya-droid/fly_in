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
        self.line_number = line_number
        self.reason = reason
        super().__init__(f"line {line_number}: {reason}")


class ZoneNotFoundError(FlyInError):
    """Raised when a zone name cannot be found in the network.

    Attributes:
        zone_name: The name that was looked up and not found.
    """

    def __init__(self, zone_name: str) -> None:
        self.zone_name = zone_name
        super().__init__(f"zone not found: {zone_name}")


class SimulationError(FlyInError):
    """Raised when the simulation reaches an illegal or unresolvable state."""
