"""RunRecorder: what the simulation did each turn, for a JSON file.

``--save-run`` writes one entry per turn: the moves of the turn and the
``SimulationState`` after it. Turn 0 is the initial state. The state lists
where each drone not delivered yet is; delivered drones are only counted,
so that the file stays small on maps with thousands of drones:

    {"format": "fly_in.run", "version": 1, "nb_drones": 5,
     "complete": true,
     "turns": [{"turn": 1, "log": "D1-roof1 D2-corridorA",
                "moves": [{"drone_id": 1, "destination": "roof1",
                           "connection": "hub-roof1"}, ...],
                "delivered_count": 0,
                "drones": [{"drone_id": 1, "status": "at_zone",
                            "zone": "roof1", "connection": null,
                            "target": null}, ...]}, ...]}
"""

from ..models.drone import Drone
from ..output.formatter import TurnLogFormatter
from ..simulation.state import Move, SimulationState
from .json_file import write_json

RUN_FORMAT = "fly_in.run"
"""The ``format`` value of a run file."""

RUN_VERSION = 1
"""The ``version`` value of the run files this code writes."""


def move_to_json(move: Move) -> dict[str, object]:
    """Return one move as plain JSON values."""
    return {
        "drone_id": move.drone_id,
        "destination": move.destination,
        "connection": move.connection_name,
    }


def drone_to_json(drone: Drone) -> dict[str, object]:
    """Return one drone's position as plain JSON values."""
    return {
        "drone_id": drone.drone_id,
        "status": drone.status.value,
        "zone": drone.current_zone,
        "connection": drone.in_transit_connection,
        "target": drone.transit_target,
    }


def state_to_json(state: SimulationState) -> dict[str, object]:
    """Return where the drones are between turns, as plain JSON values."""
    return {
        "delivered_count": state.delivered_count,
        "drones": [drone_to_json(d) for d in state.active_drones()],
    }


class RunRecorder:
    """Follows the simulation like a view and keeps every turn.

    It is a ``TurnObserver``: ``begin`` keeps turn 0, ``render`` keeps
    each turn as it is applied. It only reads the state and writes
    nothing until ``write`` is called, so that the ``Application``
    decides what happens when writing fails.
    """

    def __init__(self) -> None:
        """Start with no turns."""
        self._turns: list[dict[str, object]] = []
        self._nb_drones = 0
        self._complete = False
        self._formatter = TurnLogFormatter()

    def begin(self, state: SimulationState) -> None:
        """Keep the initial state as turn 0."""
        self._nb_drones = len(state.drones)
        self._keep(state, [])

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Keep the turn's moves and the state after it."""
        self._keep(state, moves)

    def close(self) -> None:
        """Do nothing: the file is written by ``write``."""

    def to_json(self) -> dict[str, object]:
        """Return the run so far as plain JSON values.

        ``complete`` is false when the run stopped before every drone was
        delivered (the simulation failed part-way).
        """
        return {
            "format": RUN_FORMAT,
            "version": RUN_VERSION,
            "nb_drones": self._nb_drones,
            "complete": self._complete,
            "turns": list(self._turns),
        }

    def write(self, path: str) -> None:
        """Write the run so far to ``path``.

        Raises:
            droneflow.errors.OutputFileError: If the file cannot be
                written.
        """
        write_json(path, self.to_json())

    def _keep(self, state: SimulationState, moves: list[Move]) -> None:
        self._complete = state.is_complete
        self._turns.append({
            "turn": state.turn_number,
            "log": self._formatter.format_turn(moves),
            "moves": [move_to_json(move) for move in moves],
            **state_to_json(state),
        })
