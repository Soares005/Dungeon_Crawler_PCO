"""The six base elements. Each one is an automatic weapon.

Element is an abstract base class. Every subclass overrides fire() with its
own attack pattern and improve_special() with its own unique upgrade - that
is the polymorphism the rest of the game relies on: the player just calls
element.update() on whatever elements it owns.
"""
from abc import ABC, abstractmethod

from pygame.math import Vector2

from settings import (ELEMENT_COLORS, MAX_ELEMENT_LEVEL,
                      FIRE, WATER, LIGHTNING, ICE, EARTH, WIND)
from projectiles import Fireball, WaterBolt, IceShard, Rock, WindBlade
from status import Electrified


def spread_directions(base, count, spread_deg):
    """Return `count` unit vectors fanned around `base` (total spread in degrees)."""
    if count <= 1:
        return [Vector2(base)]
    step = spread_deg / (count - 1)
    start = -spread_deg / 2
    return [Vector2(base).rotate(start + step * i) for i in range(count)]


class Element(ABC):
    element_id = "neutral"
    name = "Element"
    attack_name = "Attack"
    effect_text = ""
    special_title = "Special"
    base_cooldown = 1.0
    base_damage = 10.0
    base_range = 450.0

    def __init__(self, level=1):
        self._level = max(1, min(MAX_ELEMENT_LEVEL, int(level)))
        self._timer = 0.4
        self._last_cooldown = self.base_cooldown
        self._special = 1.0          # multiplier improved by element-specific upgrades

    # -- read-only -----------------------------------------------------------
    @property
    def level(self):
        return self._level

    @property
    def is_max_level(self):
        return self._level >= MAX_ELEMENT_LEVEL

    @property
    def color(self):
        return ELEMENT_COLORS[self.element_id]

    @property
    def cooldown_ratio(self):
        """0 = just fired, 1 = ready (for the HUD)."""
        if self._last_cooldown <= 0:
            return 1.0
        return 1.0 - max(0.0, min(1.0, self._timer / self._last_cooldown))

    @property
    def special(self):
        return self._special

    # -- upgrades ------------------------------------------------------------
    def level_up(self, amount=1):
        before = self._level
        self._level = min(MAX_ELEMENT_LEVEL, self._level + max(0, int(amount)))
        return self._level - before

    def improve_special(self, power):
        """Element-specific upgrade. Subclasses describe what it means."""
        self._special += 0.25 * power

    def special_text(self, power):
        return f"+{int(25 * power)}% {self.special_title.lower()}"

    # -- combat numbers --------------------------------------------------------
    def damage(self, player):
        return self.base_damage * (1 + 0.2 * (self._level - 1)) * player.stats.damage_mult

    def cooldown(self, player):
        return self.base_cooldown * (0.95 ** (self._level - 1)) / player.stats.attack_speed

    def size(self, player):
        return player.stats.projectile_size

    # -- main loop ---------------------------------------------------------------
    def update(self, dt, world, player):
        self._timer -= dt
        if self._timer <= 0:
            if self.fire(world, player):
                self._last_cooldown = self.cooldown(player)
                self._timer = self._last_cooldown
            else:
                self._timer = 0.1        # nothing to shoot at: check again soon

    @abstractmethod
    def fire(self, world, player):
        """Perform one attack. Return True if something was fired."""

    def _aim(self, world, player):
        target = world.nearest_enemy(player.pos, self.base_range)
        if target is None:
            return None
        direction = target.pos - player.pos
        if direction.length_squared() == 0:
            return Vector2(1, 0)
        return direction.normalize()


class FireElement(Element):
    element_id = FIRE
    name = "Fire"
    attack_name = "Fireballs"
    effect_text = "Explodes on impact and sets enemies Burning."
    special_title = "Fire damage"
    base_cooldown = 1.15
    base_damage = 14

    def damage(self, player):
        return super().damage(player) * self._special

    def fire(self, world, player):
        aim = self._aim(world, player)
        if aim is None:
            return False
        count = 1 + (self._level >= 3) + (self._level >= 6) + player.stats.extra_projectiles
        size = self.size(player)
        dmg = self.damage(player)
        for direction in spread_directions(aim, count, 14 * (count - 1)):
            world.spawn_projectile(Fireball(player.pos, direction * 380, dmg, 9 * size,
                                            burn_dps=dmg * 0.3, burn_time=3.0,
                                            blast_radius=42 * size))
        world.events.push("sound", player.pos, text="fire")
        return True


class WaterElement(Element):
    element_id = WATER
    name = "Water"
    attack_name = "Water bolts"
    effect_text = "Piercing bolts that make enemies Wet."
    special_title = "Wet duration"
    base_cooldown = 0.95
    base_damage = 9

    def fire(self, world, player):
        aim = self._aim(world, player)
        if aim is None:
            return False
        count = 1 + (self._level >= 3) + (self._level >= 5) + (self._level >= 7) \
            + player.stats.extra_projectiles
        size = self.size(player)
        dmg = self.damage(player)
        wet_time = 4.0 * self._special
        for direction in spread_directions(aim, count, 12 * (count - 1)):
            world.spawn_projectile(WaterBolt(player.pos, direction * 440, dmg, 8 * size,
                                             wet_time=wet_time, pierce=2 + self._level // 4))
        world.events.push("sound", player.pos, text="water")
        return True


class LightningElement(Element):
    element_id = LIGHTNING
    name = "Lightning"
    attack_name = "Chain bolts"
    effect_text = "Instant bolt that chains between nearby enemies."
    special_title = "Chain count"
    base_cooldown = 1.35
    base_damage = 16
    base_range = 420

    def __init__(self, level=1):
        super().__init__(level)
        self._bonus_chains = 0

    @property
    def chains(self):
        return 2 + self._level // 3 + self._bonus_chains

    def improve_special(self, power):
        self._bonus_chains += max(1, int(round(power)))

    def special_text(self, power):
        return f"+{max(1, int(round(power)))} chain jumps"

    def fire(self, world, player):
        strikes = 1 + (self._level >= 4) + (self._level >= 8) + player.stats.extra_projectiles // 2
        dmg = self.damage(player)
        freezing = player.has_fusion("frozen_thunder")   # fusion passive
        fired = False
        used = set()
        for _ in range(strikes):
            target = world.random_enemy_in_range(player.pos, self.base_range, exclude=used)
            if target is None:
                break
            used.add(id(target))
            fired = True

            def on_hit(enemy, frozen=freezing, d=dmg):
                enemy.apply_status(Electrified(2.0, d * 0.1))
                if frozen and enemy.add_chill(1, 0.4, 1.5, 1.2):
                    world.events.push("freeze", enemy.pos, color=ELEMENT_COLORS[ICE])

            world.chain_lightning(player.pos, target, dmg,
                                  self.chains + player.stats.extra_projectiles, 150,
                                  on_hit=on_hit)
        if fired:
            world.events.push("sound", player.pos, text="zap")
        return fired


class IceElement(Element):
    element_id = ICE
    name = "Ice"
    attack_name = "Ice shards"
    effect_text = "A fan of shards that Slow; enough hits Freeze."
    special_title = "Slow duration"
    base_cooldown = 1.1
    base_damage = 8

    def fire(self, world, player):
        aim = self._aim(world, player)
        if aim is None:
            return False
        count = 3 + (self._level >= 4) + (self._level >= 7) + player.stats.extra_projectiles
        size = self.size(player)
        dmg = self.damage(player)
        slow = min(0.7, 0.35 + 0.03 * self._level)
        for direction in spread_directions(aim, count, 10 * (count - 1)):
            world.spawn_projectile(IceShard(player.pos, direction * 480, dmg, 6 * size,
                                            slow=slow, slow_time=1.8 * self._special,
                                            freeze_time=1.0 + 0.1 * self._level))
        world.events.push("sound", player.pos, text="ice")
        return True


class EarthElement(Element):
    element_id = EARTH
    name = "Earth"
    attack_name = "Boulders"
    effect_text = "Heavy rocks: high damage and strong knockback."
    special_title = "Knockback"
    base_cooldown = 1.75
    base_damage = 30

    def fire(self, world, player):
        aim = self._aim(world, player)
        if aim is None:
            return False
        count = 1 + (self._level >= 5) + (self._level >= 8) + player.stats.extra_projectiles // 2
        size = self.size(player)
        dmg = self.damage(player)
        for direction in spread_directions(aim, count, 20 * (count - 1)):
            world.spawn_projectile(Rock(player.pos, direction * 330, dmg, 14 * size,
                                        knockback=280 * self._special,
                                        pierce=2 + self._level // 3))
        world.events.push("sound", player.pos, text="rock")
        return True


class WindElement(Element):
    element_id = WIND
    name = "Wind"
    attack_name = "Air blades"
    effect_text = "Very fast piercing blades in the direction you move."
    special_title = "Blade speed"
    base_cooldown = 0.45
    base_damage = 7

    def fire(self, world, player):
        facing = player.facing
        extra = player.stats.extra_projectiles
        directions = spread_directions(facing, 1 + extra, 10 * extra)
        if self._level >= 3:
            directions.append(-facing)
        if self._level >= 6:
            directions += [facing.rotate(90), facing.rotate(-90)]
        size = self.size(player)
        dmg = self.damage(player)
        speed = 640 * self._special
        for direction in directions:
            world.spawn_projectile(WindBlade(player.pos, direction * speed, dmg, 11 * size,
                                             pierce=3 + self._level // 2))
        world.events.push("sound", player.pos, text="wind")
        return True


# Data-driven registry: adding a new element = write a subclass + add it here.
ELEMENT_CLASSES = {cls.element_id: cls for cls in
                   (FireElement, WaterElement, LightningElement, IceElement, EarthElement, WindElement)}


def create_element(element_id, level=1):
    cls = ELEMENT_CLASSES.get(element_id)
    if cls is None:
        raise ValueError(f"Unknown element: {element_id!r}")
    return cls(level)


def element_display_name(element_id):
    cls = ELEMENT_CLASSES.get(element_id)
    return cls.name if cls else str(element_id).title()
