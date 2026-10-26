"""Color names to RGB, shared by the terminal view and the matplotlib window.

The subject accepts any single-word string as a zone color, with no fixed
list. This table covers the common names, including every color used by
the maps handed out with the subject except ``rainbow`` (not a single
color, so it is deliberately left out). For a name not in the table,
``rgb`` returns None and each view falls back on its own default
instead of failing.
"""

RGB = tuple[int, int, int]

_NAMED_RGB: dict[str, RGB] = {
    "black": (40, 40, 40),
    "white": (245, 245, 245),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "silver": (192, 192, 192),
    "red": (220, 40, 40),
    "darkred": (139, 0, 0),
    "crimson": (220, 20, 60),
    "maroon": (128, 0, 0),
    "pink": (255, 150, 180),
    "orange": (255, 140, 0),
    "brown": (150, 85, 40),
    "gold": (255, 200, 0),
    "yellow": (240, 220, 30),
    "lime": (50, 230, 50),
    "green": (30, 160, 60),
    "darkgreen": (0, 100, 0),
    "olive": (128, 128, 0),
    "teal": (0, 128, 128),
    "cyan": (0, 200, 220),
    "blue": (40, 90, 230),
    "navy": (0, 0, 128),
    "purple": (140, 50, 170),
    "violet": (200, 120, 230),
    "magenta": (230, 0, 230),
}


def rgb(name: str | None) -> RGB | None:
    """Return the RGB triple for a color name, ignoring case.

    Args:
        name: A color name from the map, or None.

    Returns:
        The color, or None if the name is None or not in the table.
    """
    if name is None:
        return None
    return _NAMED_RGB.get(name.lower())
