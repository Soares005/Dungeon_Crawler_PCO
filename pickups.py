"""Things the player can collect: XP crystals, healing orbs, magnets and boss cores.

Pickup is the base class; each subclass overrides on_collect() to decide what
happens when the player touches it (polymorphism).
"""
from abc import ABC, abstractmethod

from pygame.math import Vector2


class Pickup(ABC):
    kind = "pickup"
    radius = 8
    color = (255, 255, 255)

    def __init__(self, pos):
        self._pos = Vector2(pos)
        self._speed = 180.0
        self._magnetized = False
        self._collected = False
        self._age = 0.0

    @property
    def pos(self):
        return Vector2(self._pos)

    @property
    def collected(self):
        return self._collected

    @property
    def age(self):
        return self._age

    def magnetize(self):
        self._magnetized = True

    def always_magnetic(self):
        """Special pickups fly to the player from further away."""
        return False

    def update(self, dt, player):
        """Move toward the player once inside the pickup radius.

        Returns True when the player touched it this frame.
        """
        self._age += dt
        to_player = player.pos - self._pos
        dist_sq = to_player.length_squared()
        reach = player.stats.pickup_radius * (2.2 if self.always_magnetic() else 1.0)
        if not self._magnetized and dist_sq < reach * reach:
            self._magnetized = True
        if self._magnetized and dist_sq > 1:
            # accelerate toward the player so the crystal "snaps" in nicely
            self._speed = min(1100.0, self._speed + 1600.0 * dt)
            step = min(self._speed * dt, dist_sq ** 0.5)
            self._pos += to_player.normalize() * step
        touch = player.radius + self.radius
        return (player.pos - self._pos).length_squared() < touch * touch

    def collect(self, player, world):
        if self._collected:
            return
        self._collected = True
        self.on_collect(player, world)

    @abstractmethod
    def on_collect(self, player, world):
        """What the pickup does to the player/world."""


class XPGem(Pickup):
    kind = "xp"

    def __init__(self, pos, value):
        super().__init__(pos)
        self._value = max(1, int(value))

    @property
    def value(self):
        return self._value

    @property
    def radius(self):
        return 5 if self._value < 5 else 7 if self._value < 20 else 10

    @property
    def color(self):
        if self._value < 5:
            return (90, 200, 255)
        if self._value < 20:
            return (110, 255, 140)
        return (255, 90, 120)

    def absorb(self, other_value):
        """Merge another gem's value into this one (keeps gem count low)."""
        self._value += int(other_value)

    def on_collect(self, player, world):
        world.give_xp(self._value)
        world.events.push("pickup", self._pos, color=self.color)


class HealOrb(Pickup):
    kind = "heal"
    radius = 9
    color = (255, 90, 120)

    def on_collect(self, player, world):
        amount = player.stats.max_hp * 0.25
        player.heal(amount)
        world.events.push("heal", self._pos, color=self.color, value=amount)


class Magnet(Pickup):
    kind = "magnet"
    radius = 10
    color = (200, 200, 255)

    def on_collect(self, player, world):
        world.magnetize_all_gems()
        world.events.push("text", self._pos, color=self.color, text="MAGNET!")


class ElementalCore(Pickup):
    """Special boss reward: full heal and a guaranteed Epic+ upgrade choice."""
    kind = "core"
    radius = 16
    color = (255, 210, 90)

    def always_magnetic(self):
        return True

    def on_collect(self, player, world):
        player.heal(player.stats.max_hp)
        world.grant_reward_choice()
        world.events.push("core", self._pos, color=self.color, text="ELEMENTAL CORE!", big=True)
