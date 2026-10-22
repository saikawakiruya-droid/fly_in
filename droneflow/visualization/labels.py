"""Texts shown by the graphical view, built without pygame.

Measuring text needs a font, so the functions that fit text to a width
take the measuring function as an argument and need no pygame themselves.
"""

from collections.abc import Callable, Sequence

from ..models.zone import Zone, ZoneRole, ZoneType
from ..simulation.state import SimulationState

Measure = Callable[[str], int]
"""Returns the width of a text in pixels."""

ROLE_SUFFIX: dict[ZoneRole, str] = {
    ZoneRole.START: " (start)",
    ZoneRole.END: " (end)",
}
"""What follows the name of the start and end zones."""


def zone_title(zone: Zone, measure: Measure, max_width: int) -> str:
    """Return the zone's name, cut with ``~`` to fit ``max_width``.

    The start and end zones get `` (start)`` / `` (end)`` after the name.
    The suffix is never cut and does not count toward ``max_width``, so
    their names get as much room as any other zone's.
    """
    suffix = ROLE_SUFFIX.get(zone.role, "")
    return fit_text(zone.name, measure, max_width) + suffix


def fit_text(text: str, measure: Measure, max_width: int) -> str:
    """Shorten text with a trailing ``~`` until it fits the width.

    At least one character and the ``~`` are kept, even if they do not
    fit.
    """
    if measure(text) <= max_width:
        return text
    while len(text) > 1 and measure(text + "~") > max_width:
        text = text[:-1]
    return text + "~"


def load_label(state: SimulationState, zone: Zone) -> str | None:
    """Return the count shown under a zone, or None for a blocked one.

    A zone with a capacity shows ``occupancy/capacity``, followed by
    ``+N`` for the drones in flight toward it (they land on the next
    turn), so a restricted zone about to be left and entered on the same
    turn reads ``1/1 +1`` rather than over capacity. The end zone shows
    how many drones were delivered, the start zone how many are in it.
    """
    if zone.zone_type is ZoneType.BLOCKED:
        return None
    if zone.role is ZoneRole.END:
        return f"{state.delivered_count} in"
    occupancy = state.occupancy(zone.name)
    capacity = zone.capacity
    if capacity is None:
        return str(occupancy)
    label = f"{occupancy}/{capacity}"
    if arriving := state.reserved(zone.name):
        label += f" +{arriving}"
    return label


def fit_items(items: Sequence[str], measure: Measure, max_width: int) -> str:
    """Join items with spaces, as many as fit, then ``... +K more``.

    Items are kept whole and in order. Nothing given gives ``-``. The
    number of items kept is found by bisection, so a turn with thousands
    of moves is measured only a few times.
    """
    if not items:
        return "-"
    whole = " ".join(items)
    if measure(whole) <= max_width:
        return whole
    low, high = 0, len(items) - 1
    while low < high:
        middle = (low + high + 1) // 2
        if measure(_shortened(items, middle)) <= max_width:
            low = middle
        else:
            high = middle - 1
    return _shortened(items, low)


def _shortened(items: Sequence[str], count: int) -> str:
    """Return the first ``count`` items and how many were left out."""
    rest = f"... +{len(items) - count} more"
    return " ".join([*items[:count], rest])
