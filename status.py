"""Status effects (Burning, Wet, Frozen, Slowed, Electrified).

Every effect is a subclass of StatusEffect and overrides the hooks it needs
(polymorphism): tick() for damage over time, speed_multiplier() for movement
and damage_taken_multiplier() for vulnerability.
"""
from abc import ABC

from settings import STATUS_COLORS, FIRE, LIGHTNING


class StatusEffect(ABC):
    """Base class: a timed effect attached to one enemy."""
    name = "status"

    def __init__(self, duration):
        self._remaining = max(0.0, float(duration))
        self._duration = self._remaining

    # -- read-only information -------------------------------------------
    @property
    def remaining(self):
        return self._remaining

    @property
    def expired(self):
        return self._remaining <= 0

    @property
    def color(self):
        return STATUS_COLORS[self.name]

    # -- behaviour --------------------------------------------------------
    def refresh(self, other):
        """Called when the same status is applied again: keep the strongest."""
        self._remaining = max(self._remaining, other.remaining)
        self._duration = max(self._duration, other.remaining)

    def update(self, dt):
        """Advance time and return damage dealt this frame (0 for most)."""
        self._remaining -= dt
        return self.tick(dt)

    def tick(self, dt):
        return 0.0

    def damage_element(self):
        return None

    def speed_multiplier(self):
        return 1.0

    def damage_taken_multiplier(self):
        return 1.0


class Burning(StatusEffect):
    name = "burning"

    def __init__(self, duration, dps):
        super().__init__(duration)
        self._dps = float(dps)

    @property
    def dps(self):
        return self._dps

    def refresh(self, other):
        super().refresh(other)
        self._dps = max(self._dps, getattr(other, "dps", 0.0))

    def tick(self, dt):
        return self._dps * dt

    def damage_element(self):
        return FIRE


class Wet(StatusEffect):
    name = "wet"

    def speed_multiplier(self):
        return 0.9


class Frozen(StatusEffect):
    name = "frozen"

    def speed_multiplier(self):
        return 0.0          # frozen enemies cannot move or attack

    def damage_taken_multiplier(self):
        return 1.1


class Slowed(StatusEffect):
    name = "slowed"

    def __init__(self, duration, strength):
        super().__init__(duration)
        self._strength = min(0.85, max(0.0, float(strength)))

    @property
    def strength(self):
        return self._strength

    def refresh(self, other):
        super().refresh(other)
        self._strength = max(self._strength, getattr(other, "strength", 0.0))

    def speed_multiplier(self):
        return 1.0 - self._strength


class Electrified(StatusEffect):
    name = "electrified"

    def __init__(self, duration, dps=2.0):
        super().__init__(duration)
        self._dps = float(dps)

    @property
    def dps(self):
        return self._dps

    def refresh(self, other):
        super().refresh(other)
        self._dps = max(self._dps, getattr(other, "dps", 0.0))

    def tick(self, dt):
        return self._dps * dt

    def damage_element(self):
        return LIGHTNING

    def speed_multiplier(self):
        return 0.85

    def damage_taken_multiplier(self):
        return 1.2          # electrified enemies take 20% more damage


class StatusSet:
    """The collection of statuses on one enemy (a dict name -> effect)."""

    def __init__(self):
        self._effects = {}

    def apply(self, effect):
        current = self._effects.get(effect.name)
        if current is None:
            self._effects[effect.name] = effect
        else:
            current.refresh(effect)

    def has(self, name):
        return name in self._effects

    def remove(self, name):
        self._effects.pop(name, None)

    def names(self):
        return list(self._effects.keys())

    def effects(self):
        return list(self._effects.values())

    def update(self, dt):
        """Tick every effect. Returns {element: damage} from damage-over-time."""
        damage = {}
        expired = []
        for name, effect in self._effects.items():
            amount = effect.update(dt)
            if amount > 0:
                element = effect.damage_element()
                damage[element] = damage.get(element, 0.0) + amount
            if effect.expired:
                expired.append(name)
        for name in expired:
            del self._effects[name]
        return damage

    def speed_multiplier(self):
        mult = 1.0
        for effect in self._effects.values():
            mult *= effect.speed_multiplier()
        return mult

    def damage_taken_multiplier(self):
        mult = 1.0
        for effect in self._effects.values():
            mult *= effect.damage_taken_multiplier()
        return mult
