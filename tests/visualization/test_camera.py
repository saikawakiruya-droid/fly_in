"""Tests for droneflow.visualization.camera (no pygame needed).

Decision 2026-10-22 "zoom and pan the graphical view"; test design
``2026-10-22_test-design-visual-zoom.md`` A (CA01-CA08).
"""

import pytest

from droneflow.visualization.camera import MIN_ZOOM, Camera, visible


def test_starts_on_the_whole_map() -> None:
    """CA01: zoom 1 and no offset: the map as laid out."""
    camera = Camera(8)

    assert camera.zoom == 1
    assert camera.offset == (0, 0)
    assert camera.to_screen((10, 20)) == (10, 20)


def test_screen_and_map_round_trip() -> None:
    """CA02: to_map undoes to_screen."""
    camera = Camera(8)
    camera.zoom = 2
    camera.offset = (5, -3)

    assert camera.to_screen((10, 20)) == (25, 37)
    assert camera.to_map((25, 37)) == (10, 20)


def test_zoom_keeps_the_point_under_the_mouse() -> None:
    """CA03: the map point under the mouse stays under it."""
    camera = Camera(8)

    for _ in range(3):
        under = camera.to_map((300, 200))
        camera.zoom_at((300, 200), 1.25)
        x, y = camera.to_screen((round(under[0]), round(under[1])))
        assert abs(x - 300) <= 2 and abs(y - 200) <= 2

    assert camera.zoom == pytest.approx(1.25 ** 3)


def test_zoom_limits() -> None:
    """CA04: the zoom stays between MIN_ZOOM and max_zoom."""
    camera = Camera(8)
    for _ in range(20):
        camera.zoom_at((0, 0), 1.25)
    assert camera.zoom == 8
    for _ in range(40):
        camera.zoom_at((0, 0), 0.8)
    assert camera.zoom == MIN_ZOOM == 0.5


def test_max_zoom_is_at_least_one() -> None:
    """CA05: a map already readable can still not shrink max below 1."""
    camera = Camera(0.3)

    camera.zoom_at((0, 0), 2)

    assert camera.zoom == 1


def test_pan() -> None:
    """CA06: dragging moves the map by the same screen distance."""
    camera = Camera(8)

    camera.pan(10, -4)

    assert camera.to_screen((0, 0)) == (10, -4)


def test_fit() -> None:
    """CA07: fit goes back to the whole map."""
    camera = Camera(8)
    camera.zoom_at((50, 50), 2)
    camera.pan(30, 30)

    camera.fit()

    assert camera.zoom == 1
    assert camera.offset == (0, 0)


@pytest.mark.parametrize(
    ("point", "inside"),
    [((0, 0), True), ((105, 55), True), ((106, 0), False), ((0, -6), False)],
)
def test_visible(point: tuple[int, int], inside: bool) -> None:
    """CA08: on screen, give or take the margin."""
    assert visible(point, (100, 50), 5) is inside
