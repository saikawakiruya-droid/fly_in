"""Camera: which part of the laid-out map the window shows, and how big.

The layout places every zone once, in "map pixels", so that the whole map
fits the window. The camera then maps those to screen pixels:

    screen = map * zoom + offset

Zoom 1 with no offset shows the whole map as laid out. Zones, text and
lines keep the same size on screen at every zoom; only the distances
between them grow or shrink, so zooming in on a huge map spreads its
zones apart until their names can be read.
"""

Point = tuple[int, int]

ZOOM_STEP = 1.25
"""How much one mouse wheel notch zooms in or out."""

MIN_ZOOM = 0.5
"""How far out the map can be zoomed (half of the fitted size)."""


class Camera:
    """Zoom and offset from map pixels to screen pixels."""

    def __init__(self, max_zoom: float) -> None:
        """Start on the whole map (zoom 1, no offset).

        Args:
            max_zoom: How far in the map can be zoomed; at least 1.
        """
        self.max_zoom = max(max_zoom, 1.0)
        self.zoom = 1.0
        self.offset = (0.0, 0.0)

    def fit(self) -> None:
        """Go back to the whole map."""
        self.zoom = 1.0
        self.offset = (0.0, 0.0)

    def to_screen(self, point: Point) -> Point:
        """Return where a map point is drawn on screen.

        Args:
            point: A point in map pixels.

        Returns:
            The point in screen pixels, rounded.
        """
        return (
            round(point[0] * self.zoom + self.offset[0]),
            round(point[1] * self.zoom + self.offset[1]),
        )

    def to_map(self, point: Point) -> tuple[float, float]:
        """Return the map point drawn at a screen point.

        Args:
            point: A point in screen pixels.

        Returns:
            The point in map pixels, not rounded.
        """
        return (
            (point[0] - self.offset[0]) / self.zoom,
            (point[1] - self.offset[1]) / self.zoom,
        )

    def zoom_at(self, screen: Point, factor: float) -> None:
        """Zoom by ``factor``, keeping the map point under ``screen`` still.

        The zoom stays between ``MIN_ZOOM`` and ``max_zoom``.

        Args:
            screen: The screen point to zoom around (the mouse).
            factor: What to multiply the zoom by; above 1 zooms in.
        """
        mx, my = self.to_map(screen)
        self.zoom = min(max(self.zoom * factor, MIN_ZOOM), self.max_zoom)
        self.offset = (screen[0] - mx * self.zoom, screen[1] - my * self.zoom)

    def pan(self, dx: int, dy: int) -> None:
        """Move the map by a mouse drag of ``(dx, dy)`` screen pixels.

        Args:
            dx: Horizontal drag in screen pixels.
            dy: Vertical drag in screen pixels.
        """
        self.offset = (self.offset[0] + dx, self.offset[1] + dy)


def visible(point: Point, size: Point, margin: int) -> bool:
    """Return whether a screen point is on screen, give or take a margin.

    Args:
        point: A point in screen pixels.
        size: The window size in pixels.
        margin: How many pixels outside the window still count.

    Returns:
        True if the point is within the window grown by ``margin``.
    """
    return (
        -margin <= point[0] <= size[0] + margin
        and -margin <= point[1] <= size[1] + margin
    )
