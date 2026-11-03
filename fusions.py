"""Elemental Fusions: powerful abilities created by combining two elements.

The system is data-driven. FUSION_RECIPES is a list of FusionRecipe records
that say *which* two elements combine, *which* Fusion subclass implements the
ability and its base numbers. To add a new combination you write one Fusion
subclass (or reuse an existing one with different numbers) and add one
recipe line - nothing else in the combat code changes.
"""
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pygame.math import Vector2

from settings import (ELEMENT_COLORS, MAX_FUSION_LEVEL, FUSION_MIN_ELEMENT_LEVEL,
                      FIRE, WATER, LIGHTNING, ICE, EARTH, WIND)
from status import Electrified, Frozen
from zones import (SteamCloud, FireTornado, Meteor, ElectricStormAura, BlizzardAura,
                   MagneticField, Sandstorm, CrystalSpike, ThunderCloud)


@dataclass(frozen=True)
class FusionRecipe:
    fusion_id: str
    name: str
    elements: frozenset
    cls: type
    damage: float
    cooldown: float
    count: int
    count_label: str          # what "+1 count" means for this fusion ("" = not upgradable)
    description: str
    color: tuple

    def is_eligible(self, player):
        """Both elements owned (at level 2+) and the fusion not unlocked yet."""
        for element_id in self.elements:
            element = player.get_element(element_id)
            if element is None or element.level < FUSION_MIN_ELEMENT_LEVEL:
                return False
        return not player.has_fusion(self.fusion_id)

    def create(self):
        return self.cls(self)


class Fusion(ABC):
    def __init__(self, recipe):
        self._recipe = recipe
        self._level = 1
        self._timer = 1.0
        self._last_cooldown = recipe.cooldown
        self._damage_mult = 1.0
        self._cooldown_mult = 1.0
        self._area_mult = 1.0
        self._bonus_count = 0

    # -- read-only -----------------------------------------------------------
    @property
    def fusion_id(self):
        return self._recipe.fusion_id

    @property
    def name(self):
        return self._recipe.name

    @property
    def color(self):
        return self._recipe.color

    @property
    def elements(self):
        return tuple(sorted(self._recipe.elements))

    @property
    def level(self):
        return self._level

    @property
    def is_max_level(self):
        return self._level >= MAX_FUSION_LEVEL

    @property
    def supports_count(self):
        return bool(self._recipe.count_label)

    @property
    def count_label(self):
        return self._recipe.count_label

    @property
    def cooldown_ratio(self):
        if self._last_cooldown <= 0:
            return 1.0
        return 1.0 - max(0.0, min(1.0, self._timer / self._last_cooldown))

    # -- numbers ---------------------------------------------------------------
    def damage(self, player):
        return (self._recipe.damage * self._damage_mult * player.stats.damage_mult
                * (1 + 0.08 * (self._level - 1)))

    def cooldown(self, player):
        return max(0.6, self._recipe.cooldown * self._cooldown_mult / player.stats.attack_speed)

    def area(self, player):
        return self._area_mult * (1 + (player.stats.projectile_size - 1) * 0.5)

    def count(self):
        return self._recipe.count + self._bonus_count

    # -- upgrades --------------------------------------------------------------
    def upgrade(self, stat, power):
        """Improve one aspect. stat is 'damage', 'cooldown', 'area' or 'count'."""
        if stat == "damage":
            self._damage_mult += 0.3 * power
        elif stat == "cooldown":
            self._cooldown_mult *= max(0.5, 1 - 0.1 * power)
        elif stat == "area":
            self._area_mult += 0.15 * power
        elif stat == "count":
            self._bonus_count += 1 if power < 3 else 2
        else:
            raise ValueError(f"Unknown fusion stat: {stat!r}")
        self._level = min(MAX_FUSION_LEVEL, self._level + 1)

    # -- main loop ---------------------------------------------------------------
    def update(self, dt, world, player):
        self._timer -= dt
        if self._timer <= 0:
            if self.activate(world, player):
                self._last_cooldown = self.cooldown(player)
                self._timer = self._last_cooldown
                world.events.push("fusion_cast", player.pos, color=self.color, text=self.name)
            else:
                self._timer = 0.2

    @abstractmethod
    def activate(self, world, player):
        """Cast the ability. Return True if it was cast."""


# ---------------------------------------------------------------------------
# The ten fusions
# ---------------------------------------------------------------------------
class FireTornadoFusion(Fusion):
    def activate(self, world, player):
        count = self.count()
        offset = world.rng.random() * math.tau
        for i in range(count):
            angle = offset + math.tau * i / count
            direction = Vector2(math.cos(angle), math.sin(angle))
            world.spawn_effect(FireTornado(player.pos + direction * 40, direction,
                                           58 * self.area(player), 4.5, self.damage(player),
                                           burn_dps=self.damage(player) * 0.6))
        return True


class MeteorShowerFusion(Fusion):
    def activate(self, world, player):
        targets = world.enemies_in_radius(player.pos, 520)
        if not targets:
            return False
        world.rng.shuffle(targets)
        for i in range(self.count()):
            if i < len(targets):
                point = targets[i].pos
            else:
                angle = world.rng.random() * math.tau
                point = player.pos + Vector2(math.cos(angle), math.sin(angle)) * world.rng.uniform(80, 400)
            world.spawn_effect(Meteor(point, 95 * self.area(player), self.damage(player),
                                      delay=i * 0.12))
        return True


class SteamExplosionFusion(Fusion):
    def activate(self, world, player):
        fired = False
        used = []
        for _ in range(self.count()):
            center = world.densest_point(player.pos, 480, avoid=used)
            if center is None:
                break
            used.append(center)
            radius = 115 * self.area(player)
            dmg = self.damage(player)
            world.explode(center, radius, dmg, WATER, knock_force=220, shake=5,
                          color=(235, 240, 255))
            world.spawn_effect(SteamCloud(center, radius * 0.9, 3.0, dmg * 0.18))
            fired = True
        return fired


class ElectricStormFusion(Fusion):
    def activate(self, world, player):
        world.spawn_effect(ElectricStormAura(player.pos, 240 * self.area(player), 4.5,
                                             self.damage(player), links=self.count()))
        return True


class BlizzardFusion(Fusion):
    def activate(self, world, player):
        world.spawn_effect(BlizzardAura(player.pos, 175 * self.area(player), 5.0,
                                        self.damage(player)))
        return True


class MagneticFieldFusion(Fusion):
    def activate(self, world, player):
        fired = False
        used = []
        for _ in range(self.count()):
            center = world.densest_point(player.pos, 450, avoid=used)
            if center is None:
                break
            used.append(center)
            world.spawn_effect(MagneticField(center, 200 * self.area(player), 1.6,
                                             self.damage(player)))
            fired = True
        return fired


class SandstormFusion(Fusion):
    def activate(self, world, player):
        for i in range(self.count()):
            target = world.densest_point(player.pos, 500)
            if target is None:
                direction = player.facing
            else:
                direction = target - player.pos
                direction = direction.normalize() if direction.length_squared() > 0 else Vector2(1, 0)
            direction = direction.rotate(i * 360 / max(1, self.count()))
            start = player.pos - direction * 120
            world.spawn_effect(Sandstorm(start, direction, 150 * self.area(player), 6.0,
                                         self.damage(player)))
        return True


class CrystalSpikesFusion(Fusion):
    def activate(self, world, player):
        target = world.nearest_enemy(player.pos, 520)
        if target is None:
            return False
        aim = target.pos - player.pos
        aim = aim.normalize() if aim.length_squared() > 0 else Vector2(1, 0)
        lines = self.count()
        spread = 360 / lines if lines >= 5 else 28
        radius = 34 * self.area(player)
        for line in range(lines):
            direction = aim.rotate((line - (lines - 1) / 2) * spread)
            for step in range(7):
                point = player.pos + direction * (60 + step * radius * 1.5)
                world.spawn_effect(CrystalSpike(point, radius, self.damage(player), delay=step * 0.07))
        return True


class FrozenThunderFusion(Fusion):
    """Freezing lightning from the sky. (Also makes basic Lightning chill - see elements.py.)"""

    def activate(self, world, player):
        fired = False
        used = set()
        dmg = self.damage(player)
        for _ in range(self.count()):
            target = world.random_enemy_in_range(player.pos, 480, exclude=used)
            if target is None:
                break
            used.add(id(target))
            fired = True
            sky = (target.pos.x, target.pos.y - 300)
            world.events.push("lightning", target.pos, color=(190, 245, 255),
                              points=[sky, tuple(target.pos)], value=4, big=True)

            def freeze(enemy):
                enemy.apply_status(Frozen(1.6))
                enemy.apply_status(Electrified(2.0, dmg * 0.05))

            world.chain_lightning(target.pos, target, dmg, 2, 140, on_hit=freeze,
                                  color=(190, 245, 255))
        if fired:
            world.events.push("shake", player.pos, value=3)
        return fired


class ThunderstormFusion(Fusion):
    def activate(self, world, player):
        world.spawn_effect(ThunderCloud(player.pos, 170 * self.area(player), 6.0,
                                        self.damage(player), strike_interval=0.32 / (1 + 0.15 * (self.count() - 1))))
        return True


def _mix(a, b):
    ca, cb = ELEMENT_COLORS[a], ELEMENT_COLORS[b]
    return tuple((x + y) // 2 for x, y in zip(ca, cb))


FUSION_RECIPES = (
    FusionRecipe("fire_tornado", "Fire Tornado", frozenset({FIRE, WIND}), FireTornadoFusion,
                 damage=16, cooldown=5.0, count=1, count_label="tornado",
                 description="Burning tornadoes roam the arena, pulling enemies into their eye.",
                 color=(255, 140, 60)),
    FusionRecipe("meteor_shower", "Meteor Shower", frozenset({FIRE, EARTH}), MeteorShowerFusion,
                 damage=70, cooldown=4.5, count=4, count_label="meteor",
                 description="Meteors crash down on enemies, exploding and leaving burning craters.",
                 color=(255, 100, 40)),
    FusionRecipe("steam_explosion", "Steam Explosion", frozenset({FIRE, WATER}), SteamExplosionFusion,
                 damage=55, cooldown=4.0, count=1, count_label="explosion",
                 description="Blasts the biggest crowd and leaves a scalding steam cloud.",
                 color=(230, 235, 250)),
    FusionRecipe("electric_storm", "Electric Storm", frozenset({WATER, LIGHTNING}), ElectricStormFusion,
                 damage=22, cooldown=6.5, count=6, count_label="conduction link",
                 description="Rain soaks enemies around you; wet enemies conduct arcs to each other.",
                 color=_mix(WATER, LIGHTNING)),
    FusionRecipe("blizzard", "Blizzard", frozenset({WATER, ICE}), BlizzardFusion,
                 damage=9, cooldown=7.5, count=1, count_label="",
                 description="A freezing storm around you that slows and freezes everything inside.",
                 color=(190, 225, 255)),
    FusionRecipe("magnetic_field", "Magnetic Field", frozenset({EARTH, LIGHTNING}), MagneticFieldFusion,
                 damage=80, cooldown=6.0, count=1, count_label="field",
                 description="Drags enemies together, then discharges a massive electric burst.",
                 color=_mix(EARTH, LIGHTNING)),
    FusionRecipe("sandstorm", "Sandstorm", frozenset({EARTH, WIND}), SandstormFusion,
                 damage=11, cooldown=7.0, count=1, count_label="sandstorm",
                 description="A huge sweeping storm of sand that grinds and slows enemies.",
                 color=(225, 190, 120)),
    FusionRecipe("crystal_spikes", "Crystal Spikes", frozenset({ICE, EARTH}), CrystalSpikesFusion,
                 damage=34, cooldown=3.6, count=3, count_label="spike line",
                 description="Lines of ice crystals erupt from the ground, impaling and chilling.",
                 color=(170, 210, 240)),
    FusionRecipe("frozen_thunder", "Frozen Thunder", frozenset({ICE, LIGHTNING}), FrozenThunderFusion,
                 damage=42, cooldown=4.0, count=3, count_label="strike",
                 description="Freezing bolts from the sky. Your Lightning now chills enemies too.",
                 color=(190, 245, 255)),
    FusionRecipe("thunderstorm", "Thunderstorm", frozenset({WIND, LIGHTNING}), ThunderstormFusion,
                 damage=26, cooldown=7.0, count=1, count_label="storm intensity",
                 description="A drifting storm cloud that rains lightning strikes inside it.",
                 color=_mix(WIND, LIGHTNING)),
)

FUSIONS_BY_ID = {recipe.fusion_id: recipe for recipe in FUSION_RECIPES}


def eligible_recipes(player):
    return [recipe for recipe in FUSION_RECIPES if recipe.is_eligible(player)]
