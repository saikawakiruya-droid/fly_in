"""Visualizer: the interface every view implements."""

from ..simulation.observer import TurnObserver

Visualizer = TurnObserver
"""A view is a ``TurnObserver``: the engine calls ``begin``, ``render``
after every turn and ``close``. The name says what the class is for."""
