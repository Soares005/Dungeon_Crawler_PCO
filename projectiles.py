"""Projectiles fired by the player's elements and by enemies.

Projectile is the base class. Subclasses override on_hit() to apply their
element's special effect (burn, wet, chill, knockback...).
"""
from abc import ABC

from pygame.math import Vector2

from settings import ELEMENT_COLORS, FIRE, WATER, ICE, EARTH, WIND, ARENA_SIZE
from status import Burning, Wet


class Projectile(ABC):
    kind = "projectile"

    def __init__(self, pos, vel, damage, radius, element, pierce=0, lifetime=1.6):
        self._pos = Vector2(pos)
        self._vel = Vector2(vel)
        self._damage = float(damage)
        self._radius = float(radius)
        self._element = element
        self._pierce = int(pierce)
        self._lifetime = float(lifetime)
        self._age = 0.0
        self._alive = True
        self._hit_ids = set()

    # -- read-only ---------------------------------------------------------
    @property
    def pos(self):
        return Vector2(self._pos)

    @property
    def vel(self):
        return Vector2(self._vel)

    @property
    def radius(self):
        return self._radius

    @property
    def element(self):
        return self._element

    @property
    def color(self):
        return ELEMENT_COLORS.get(self._element, (255, 255, 255))

    @property
    def alive(self):
        return self._alive

    @property
    def age(self):
        return self._age

    @property
    def damage(self):
        return self._damage

    # -- behaviour -----------------------------------------------------------
    def update(self, dt):
        self._age += dt
        self._pos += self._vel * dt
        if (self._age >= self._lifetime or not -50 < self._pos.x < ARENA_SIZE + 50
                or not -50 < self._pos.y < ARENA_SIZE + 50):
            self._alive = False

    def can_hit(self, enemy):
        return self._alive and id(enemy) not in self._hit_ids

    def hit(self, enemy, world):
        """Called by the world on collision. Handles piercing bookkeeping."""
        self._hit_ids.add(id(enemy))
        self.on_hit(enemy, world)
        self._pierce -= 1
        if self._pierce < 0:
            self._alive = False

    def on_hit(self, enemy, world):
        world.damage_enemy(enemy, self._damage, self._element)


class Fireball(Projectile):
    kind = "fireball"

    def __init__(self, pos, vel, damage, radius, burn_dps, burn_time, blast_radius):
        super().__init__(pos, vel, damage, radius, FIRE, pierce=0, lifetime=1.8)
        self._burn_dps = burn_dps
        self._burn_time = burn_time
        self._blast = blast_radius

    def on_hit(self, enemy, world):
        world.damage_enemy(enemy, self._damage, FIRE)
        enemy.apply_status(Burning(self._burn_time, self._burn_dps))
        # small splash that also ignites neighbours
        world.explode(self._pos, self._blast, self._damage * 0.4, FIRE,
                      on_each=lambda e: e.apply_status(Burning(self._burn_time, self._burn_dps)),
                      exclude=enemy, quiet=True)


class WaterBolt(Projectile):
    kind = "water"

    def __init__(self, pos, vel, damage, radius, wet_time, pierce):
        super().__init__(pos, vel, damage, radius, WATER, pierce=pierce, lifetime=1.4)
        self._wet_time = wet_time

    def on_hit(self, enemy, world):
        world.damage_enemy(enemy, self._damage, WATER, knock_dir=self._vel, knock_force=60)
        enemy.apply_status(Wet(self._wet_time))


class IceShard(Projectile):
    kind = "ice"

    def __init__(self, pos, vel, damage, radius, slow, slow_time, freeze_time):
        super().__init__(pos, vel, damage, radius, ICE, pierce=1, lifetime=1.2)
        self._slow = slow
        self._slow_time = slow_time
        self._freeze_time = freeze_time

    def on_hit(self, enemy, world):
        world.damage_enemy(enemy, self._damage, ICE)
        if enemy.alive and enemy.add_chill(1, self._slow, self._slow_time, self._freeze_time):
            world.events.push("freeze", enemy.pos, color=ELEMENT_COLORS[ICE])


class Rock(Projectile):
    kind = "rock"

    def __init__(self, pos, vel, damage, radius, knockback, pierce):
        super().__init__(pos, vel, damage, radius, EARTH, pierce=pierce, lifetime=1.6)
        self._knockback = knockback

    def on_hit(self, enemy, world):
        world.damage_enemy(enemy, self._damage, EARTH, knock_dir=self._vel,
                           knock_force=self._knockback)
        world.events.push("dust", self._pos, color=ELEMENT_COLORS[EARTH])


class WindBlade(Projectile):
    kind = "wind"

    def __init__(self, pos, vel, damage, radius, pierce):
        super().__init__(pos, vel, damage, radius, WIND, pierce=pierce, lifetime=0.9)

    def on_hit(self, enemy, world):
        world.damage_enemy(enemy, self._damage, WIND, knock_dir=self._vel, knock_force=90)


class EnemyBullet(Projectile):
    """Hostile projectile: hurts the player instead of enemies."""
    kind = "enemy_bullet"

    def __init__(self, pos, vel, damage, radius, color):
        super().__init__(pos, vel, damage, radius, "enemy", pierce=0, lifetime=4.0)
        self._color = color

    @property
    def color(self):
        return self._color

    def on_hit_player(self, player, world):
        if player.take_damage(self._damage):
            world.events.push("player_hurt", player.pos, value=self._damage)
        self._alive = False
