"""Game events: the bridge between the logic layer and the presentation layer.

The combat logic never draws anything or plays sounds. Instead it *emits*
GameEvent objects ("an enemy was hit here", "a reaction happened there").
The presentation layer (effects.py) reads those events every frame and turns
them into particles, damage numbers, screen shake and sound.
"""
from dataclasses import dataclass, field


@dataclass
class GameEvent:
    """A small, immutable-by-convention message produced by the game logic."""
    kind: str                       # "hit", "death", "reaction", "explosion", ...
    pos: tuple = (0.0, 0.0)         # world position
    color: tuple = (255, 255, 255)
    value: float = 0.0              # damage, radius, strength... depends on kind
    text: str = ""
    points: list = field(default_factory=list)   # for lightning arcs, etc.
    big: bool = False


class EventQueue:
    """FIFO queue of GameEvents. Logic pushes, presentation drains."""

    def __init__(self):
        self._events = []

    def push(self, kind, pos=(0.0, 0.0), **kwargs):
        self._events.append(GameEvent(kind, (float(pos[0]), float(pos[1])), **kwargs))

    def drain(self):
        """Return every pending event and empty the queue."""
        events, self._events = self._events, []
        return events

    def __len__(self):
        return len(self._events)
