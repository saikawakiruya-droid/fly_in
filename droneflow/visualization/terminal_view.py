"""TerminalVisualizer: colored terminal rendering of the simulation."""

import os
import shutil
import sys
from typing import TextIO

from ..models.drone import Drone
from ..models.zone import Zone, ZoneRole, ZoneType
from ..simulation.state import Move, SimulationState
from .palette import rgb

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"

_TYPE_TAGS: dict[ZoneType, str] = {
    ZoneType.NORMAL: ".",
    ZoneType.PRIORITY: "P",
    ZoneType.RESTRICTED: "R",
    ZoneType.BLOCKED: "X",
}
_ROLE_TAGS: dict[ZoneRole, str] = {
    ZoneRole.START: "S",
    ZoneRole.END: "E",
}
_LEGEND = (
    "legend: S start  E end  . normal  P priority  R restricted  "
    "X blocked | "
    "in/max (- no limit, +N arriving, * full)"
)
_NAME_WIDTH_LIMIT = 18
_CELL_GAP = "   "


def color_enabled(stream: TextIO) -> bool:
    """Return whether ANSI colors should be written to the stream.

    Colors are off when the ``NO_COLOR`` environment variable is set to a
    non-empty value (https://no-color.org) or when the stream is not a
    terminal (e.g. redirected to a file).
    """
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return stream.isatty()
    except ValueError:
        return False


class _Chunk:
    """A piece of text with and without its color codes."""

    def __init__(self, plain: str, shown: str) -> None:
        self.plain = plain
        self.shown = shown


class TerminalVisualizer:
    """Renders zone occupancy and drone positions as colored terminal text.

    Every frame goes to ``stream`` (standard error by default), so that
    standard output keeps only the turn log required by the subject. All
    text is ASCII; zone names are painted with their ``color=`` metadata
    when colors are enabled, and unknown or missing colors are left in the
    terminal's default color.
    """

    def __init__(
        self,
        stream: TextIO | None = None,
        color: bool | None = None,
        width: int | None = None,
    ) -> None:
        """Choose where and how to write.

        Args:
            stream: Where frames are written; defaults to ``sys.stderr``.
            color: Force colors on or off; by default they are used only
                if ``color_enabled(stream)``.
            width: Line width used to lay out the zones; defaults to the
                terminal width (100 if unknown).
        """
        self.stream: TextIO = sys.stderr if stream is None else stream
        self.color = color_enabled(self.stream) if color is None else color
        self.width = (
            shutil.get_terminal_size((100, 24)).columns
            if width is None else width
        )

    def begin(self, state: SimulationState) -> None:
        """Write the initial state and a legend of the symbols used."""
        network = state.network
        header = (
            f"=== Turn {state.turn_number} (start) | "
            f"{len(state.drones)} drones | {len(network.zones)} zones, "
            f"{len(network.connections)} connections ==="
        )
        lines = [self._style(header, _BOLD), _LEGEND]
        lines.extend(self._state_lines(state))
        self._write(lines)

    def render(self, state: SimulationState, moves: list[Move]) -> None:
        """Write one frame: the turn's moves and the resulting state."""
        self._write(self.frame(state, moves))

    def close(self) -> None:
        """Flush the stream; it is not closed (it is not ours)."""
        self.stream.flush()

    def frame(self, state: SimulationState, moves: list[Move]) -> list[str]:
        """Return the lines describing a turn, without writing them."""
        header = (
            f"=== Turn {state.turn_number} | moved {len(moves)} | "
            f"delivered {state.delivered_count}/{len(state.drones)} ==="
        )
        lines = [self._style(header, _BOLD)]
        lines.extend(self._wrap("moves:", [
            self._move_chunk(state, move) for move in moves
        ]))
        lines.extend(self._state_lines(state))
        return lines

    def _state_lines(self, state: SimulationState) -> list[str]:
        lines = self._zone_grid(state)
        placed = [
            self._drones_chunk(state.network.zones[name], drones)
            for name, drones in self._drones_by_zone(state).items()
        ]
        lines.extend(self._wrap("drones:", placed))
        in_flight = [
            self._transit_chunk(state, drone)
            for drone in state.drones_in_transit()
        ]
        if in_flight:
            lines.extend(self._wrap("in flight:", in_flight, sep=", "))
        return lines

    def _zone_grid(self, state: SimulationState) -> list[str]:
        zones = list(state.network.zones.values())
        name_width = min(
            max((len(z.name) for z in zones), default=1), _NAME_WIDTH_LIMIT
        )
        cells = [self._zone_cell(state, z, name_width) for z in zones]
        cell_width = len(cells[0].plain) if cells else 1
        per_line = max(
            1, (self.width - 2) // (cell_width + len(_CELL_GAP))
        )
        lines = []
        for first in range(0, len(cells), per_line):
            row = cells[first:first + per_line]
            lines.append(
                ("  " + _CELL_GAP.join(c.shown for c in row)).rstrip()
            )
        return lines

    def _zone_cell(
        self, state: SimulationState, zone: Zone, name_width: int
    ) -> _Chunk:
        name = zone.name
        if len(name) > name_width:
            name = name[:name_width - 1] + "~"
        name = name.ljust(name_width)
        tag = _ROLE_TAGS.get(zone.role, _TYPE_TAGS[zone.zone_type])
        count = self._count_text(state, zone)
        full = count.endswith("*")
        padding = " " * max(0, 8 - len(count))
        plain = f"{name} {tag} {count}{padding}"
        shown = (
            f"{self._paint(name, zone.color)} {tag} "
            f"{self._style(count, _BOLD if full else '')}{padding}"
        )
        if zone.zone_type is ZoneType.BLOCKED:
            shown = self._style(plain, _DIM)
        return _Chunk(plain, shown)

    @staticmethod
    def _count_text(state: SimulationState, zone: Zone) -> str:
        if zone.zone_type is ZoneType.BLOCKED:
            return "--"
        if zone.role is ZoneRole.END:
            return f"{state.delivered_count}/-"
        inside = state.occupancy(zone.name)
        arriving = state.reserved(zone.name)
        text = str(inside)
        text += "/-" if zone.max_drones is None else f"/{zone.max_drones}"
        if arriving:
            text += f"+{arriving}"
        if zone.max_drones is not None and (
            state.load(zone.name) >= zone.max_drones
        ):
            text += "*"
        return text

    @staticmethod
    def _drones_by_zone(state: SimulationState) -> dict[str, list[int]]:
        placed: dict[str, list[int]] = {}
        for drone in state.active_drones():
            if drone.current_zone is not None:
                placed.setdefault(drone.current_zone, []).append(
                    drone.drone_id
                )
        return placed

    def _drones_chunk(self, zone: Zone, drone_ids: list[int]) -> _Chunk:
        ids = _id_ranges(drone_ids)
        return _Chunk(
            f"{zone.name}[{ids}]",
            f"{self._paint(zone.name, zone.color)}[{ids}]",
        )

    def _move_chunk(self, state: SimulationState, move: Move) -> _Chunk:
        zone = state.network.zones.get(move.destination)
        target = (
            move.destination if zone is None
            else self._paint(zone.name, zone.color)
        )
        return _Chunk(
            f"D{move.drone_id}-{move.destination}",
            f"D{move.drone_id}-{target}",
        )

    def _transit_chunk(self, state: SimulationState, drone: Drone) -> _Chunk:
        link = drone.in_transit_connection or "?"
        target = drone.transit_target or "?"
        zone = state.network.zones.get(target)
        shown_target = (
            target if zone is None else self._paint(target, zone.color)
        )
        return _Chunk(
            f"D{drone.drone_id} {link} -> {target}",
            f"D{drone.drone_id} {link} -> {shown_target}",
        )

    def _wrap(
        self, label: str, chunks: list[_Chunk], sep: str = " "
    ) -> list[str]:
        """Lay out chunks after a label, wrapping on the plain width."""
        if not chunks:
            return [f"{label} -"]
        indent = " " * len(label)
        lines: list[str] = []
        shown, used = label, len(label)
        for index, chunk in enumerate(chunks):
            joiner = " " if index == 0 else sep
            fits = used + len(joiner) + len(chunk.plain) <= self.width
            if index > 0 and not fits:
                lines.append(shown.rstrip())
                shown, used = indent, len(indent)
                joiner = " "
            shown += joiner + chunk.shown
            used += len(joiner) + len(chunk.plain)
        lines.append(shown)
        return lines

    def _paint(self, text: str, color_name: str | None) -> str:
        color = rgb(color_name)
        if not self.color or color is None:
            return text
        red, green, blue = color
        return f"\x1b[38;2;{red};{green};{blue}m{text}{_RESET}"

    def _style(self, text: str, code: str) -> str:
        if not self.color or not code:
            return text
        return f"{code}{text}{_RESET}"

    def _write(self, lines: list[str]) -> None:
        self.stream.write("\n".join(lines) + "\n")
        self.stream.flush()


def _id_ranges(drone_ids: list[int]) -> str:
    """Return ids like ``D1..D4 D7``: consecutive runs are shortened."""
    parts: list[str] = []
    ids = sorted(drone_ids)
    start = 0
    for index in range(1, len(ids) + 1):
        if index < len(ids) and ids[index] == ids[index - 1] + 1:
            continue
        low, high = ids[start], ids[index - 1]
        if high - low >= 2:
            parts.append(f"D{low}..D{high}")
        else:
            parts.extend(f"D{i}" for i in range(low, high + 1))
        start = index
    return " ".join(parts)
