"""Enemy types and the wave director that spawns them.

Enemy is an abstract base class. Each subclass overrides behave() (how it
moves/attacks) and some override on_death() (what it drops) - the world just
calls enemy.update() and never needs to know which concrete type it is.
"""
import math
from abc import ABC

from pygame.math import Vector2

from settings import (ARENA_SIZE, MAX_ENEMIES, BOSS_INTERVAL, BOSS_WARNING_TIME,
                      SPAWN_RING_MIN, SPAWN_RING_MAX)
from status import StatusSet, Frozen, Slowed
from pickups import HealOrb, Magnet, ElementalCore

CHILL_TO_FREEZE = 3


class Enemy(ABC):
    kind = "basic"
    shape = "circle"
    color = (230, 80, 110)
    base_hp = 12
    base_speed = 70
    base_damage = 8
    radius = 13
    xp = 1
    mass = 1.0
    knockback_resist = 0.0
    is_boss = False
    is_elite = False

    def __init__(self, pos, hp_mult=1.0, speed_mult=1.0, dmg_mult=1.0):
        self._pos = Vector2(pos)
        self._max_hp = self.base_hp * hp_mult
        self._hp = self._max_hp
        self._speed = self.base_speed * speed_mult
        self._damage = self.base_damage * dmg_mult
        self._knock = Vector2()
        self._statuses = StatusSet()
        self._chill = 0
        self._flash = 0.0
        self._alive = True
        self._age = 0.0
        self._dot = {}
        self._dot_timer = 0.4
        self._reaction_cd = {}
        self._facing = Vector2(1, 0)

    # ------------------------------------------------------------------
    # Read-only information used by other systems and the renderer
    # ------------------------------------------------------------------
    @property
    def pos(self):
        return Vector2(self._pos)

    @property
    def hp(self):
        return self._hp

    @property
    def max_hp(self):
        return self._max_hp

    @property
    def hp_ratio(self):
        return max(0.0, self._hp / self._max_hp)

    @property
    def alive(self):
        return self._alive

    @property
    def flash(self):
        return self._flash

    @property
    def age(self):
        return self._age

    @property
    def facing(self):
        return Vector2(self._facing)

    @property
    def contact_damage(self):
        return self._damage

    @property
    def chill(self):
        return self._chill

    def can_hit_player(self):
        return self._alive and not self._statuses.has("frozen")

    def has_status(self, name):
        return self._statuses.has(name)

    def status_names(self):
        return self._statuses.names()

    def is_telegraphing(self):
        """True while winding up a special attack (drawn as a warning)."""
        return False

    # ------------------------------------------------------------------
    # State changes - the only way other objects can modify an enemy
    # ------------------------------------------------------------------
    def take_damage(self, amount):
        """Apply damage; returns the real amount dealt after vulnerabilities."""
        if not self._alive or amount <= 0:
            return 0.0
        dealt = amount * self._statuses.damage_taken_multiplier()
        self._hp -= dealt
        self._flash = 0.09
        if self._hp <= 0:
            self._hp = 0
            self._alive = False
        return dealt

    def relocate(self, pos):
        """Used by the world to bring enemies that fell far behind back near the player."""
        self._pos = Vector2(pos)
        self._knock = Vector2()

    def apply_status(self, effect):
        if effect.name == "frozen":
            if self.is_boss:        # bosses cannot be frozen solid
                effect = Slowed(effect.remaining, 0.45)
            elif self.is_elite:
                effect = Frozen(effect.remaining * 0.5)
        self._statuses.apply(effect)

    def consume_status(self, name):
        """Remove a status; returns True if it was present (used by reactions)."""
        if self._statuses.has(name):
            self._statuses.remove(name)
            return True
        return False

    def add_chill(self, stacks, slow_strength, duration, freeze_time=1.2):
        """Ice hits stack 'chill'. Enough chill freezes the enemy.

        Returns True if this call froze the enemy.
        """
        self.apply_status(Slowed(duration, slow_strength))
        if self._statuses.has("frozen"):
            return False
        self._chill += stacks
        if self._chill >= CHILL_TO_FREEZE:
            self._chill = 0
            self.apply_status(Frozen(freeze_time))
            return True
        return False

    def knockback(self, direction, force):
        if direction.length_squared() == 0:
            return
        self._knock += direction.normalize() * force * (1.0 - self.knockback_resist)

    def pull_towards(self, point, strength, dt):
        offset = Vector2(point) - self._pos
        dist = offset.length()
        if dist > 4:
            self._pos += offset / dist * min(dist, strength * dt * (1.0 - self.knockback_resist * 0.6))

    def push(self, offset):
        """Separation push from neighbours (so enemies do not stack)."""
        self._pos += offset / self.mass

    def reaction_ready(self, reaction_id, now, cooldown):
        """Per-enemy reaction cooldown, so one enemy can't trigger 30 reactions a second."""
        if now < self._reaction_cd.get(reaction_id, -1.0):
            return False
        self._reaction_cd[reaction_id] = now + cooldown
        return True

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------
    def update(self, dt, world):
        self._age += dt
        if self._flash > 0:
            self._flash -= dt
        self._update_statuses(dt, world)
        if not self._alive:
            return
        speed_mult = self._statuses.speed_multiplier()
        if speed_mult > 0:
            self.behave(dt, world, speed_mult)
        # knockback velocity decays quickly
        if self._knock.length_squared() > 1:
            self._pos += self._knock * dt
            self._knock *= max(0.0, 1.0 - 7.0 * dt)
        self._pos.x = min(max(self._pos.x, 0), ARENA_SIZE)
        self._pos.y = min(max(self._pos.y, 0), ARENA_SIZE)

    def _update_statuses(self, dt, world):
        for element, amount in self._statuses.update(dt).items():
            self._dot[element] = self._dot.get(element, 0.0) + amount
        self._dot_timer -= dt
        if self._dot_timer <= 0:
            self._dot_timer = 0.4
            dot, self._dot = self._dot, {}
            for element, amount in dot.items():
                if amount > 0 and self._alive:
                    world.damage_enemy(self, amount, element, allow_reactions=False, is_dot=True)

    def _move_towards(self, target, speed, dt):
        offset = target - self._pos
        dist = offset.length()
        if dist > 1:
            self._facing = offset / dist
            self._pos += self._facing * min(dist, speed * dt)

    def behave(self, dt, world, speed_mult):
        """Default AI: walk straight at the player."""
        self._move_towards(world.player.pos, self._speed * speed_mult, dt)

    def on_death(self, world):
        """Default drop: XP crystals and a small chance for a goodie."""
        world.drop_xp(self._pos, self.xp, 1)
        roll = world.rng.random()
        if roll < 0.006:
            world.spawn_pickup(HealOrb(self._pos))
        elif roll < 0.008:
            world.spawn_pickup(Magnet(self._pos))


class BasicEnemy(Enemy):
    kind = "basic"


class FastEnemy(Enemy):
    kind = "fast"
    shape = "triangle"
    color = (255, 150, 60)
    base_hp = 7
    base_speed = 150
    base_damage = 6
    radius = 10
    mass = 0.7

    def behave(self, dt, world, speed_mult):
        # weave slightly from side to side so packs look like a swarm
        target = world.player.pos
        offset = target - self._pos
        if offset.length_squared() > 1:
            side = Vector2(-offset.y, offset.x).normalize() * math.sin(self._age * 5 + id(self) % 7) * 60
            target = target + side
        self._move_towards(target, self._speed * speed_mult, dt)


class TankEnemy(Enemy):
    kind = "tank"
    shape = "square"
    color = (140, 90, 200)
    base_hp = 70
    base_speed = 46
    base_damage = 18
    radius = 24
    xp = 5
    mass = 4.0
    knockback_resist = 0.75


class RangedEnemy(Enemy):
    """Keeps its distance and fires slow orbs at the player."""
    kind = "ranged"
    shape = "diamond"
    color = (80, 220, 200)
    base_hp = 16
    base_speed = 90
    base_damage = 6
    radius = 13
    xp = 2
    PREFERRED_MIN = 230
    PREFERRED_MAX = 330

    def __init__(self, pos, hp_mult=1.0, speed_mult=1.0, dmg_mult=1.0):
        super().__init__(pos, hp_mult, speed_mult, dmg_mult)
        self._shot_timer = 1.5 + (id(self) % 10) / 10

    def behave(self, dt, world, speed_mult):
        player_pos = world.player.pos
        offset = player_pos - self._pos
        dist = offset.length()
        if dist < 1:
            return
        direction = offset / dist
        self._facing = direction
        speed = self._speed * speed_mult
        if dist > self.PREFERRED_MAX:
            self._pos += direction * speed * dt
        elif dist < self.PREFERRED_MIN:
            self._pos -= direction * speed * 0.8 * dt
        else:   # strafe around the player
            self._pos += Vector2(-direction.y, direction.x) * speed * 0.5 * dt
        self._shot_timer -= dt
        if self._shot_timer <= 0 and dist < 520:
            self._shot_timer = 2.4
            world.spawn_enemy_bullet(self._pos, direction * 220, self._damage * 1.4, 7, self.color)


class EliteEnemy(Enemy):
    """Big, glowing, tough and dashes at the player every few seconds."""
    kind = "elite"
    shape = "elite"
    color = (255, 70, 160)
    base_hp = 190
    base_speed = 82
    base_damage = 16
    radius = 21
    xp = 25
    mass = 3.0
    knockback_resist = 0.6
    is_elite = True

    def __init__(self, pos, hp_mult=1.0, speed_mult=1.0, dmg_mult=1.0):
        super().__init__(pos, hp_mult, speed_mult, dmg_mult)
        self._dash_timer = 3.5
        self._windup = 0.0
        self._dash = 0.0
        self._dash_dir = Vector2(1, 0)

    def is_telegraphing(self):
        return self._windup > 0

    def behave(self, dt, world, speed_mult):
        if self._windup > 0:
            self._windup -= dt
            if self._windup <= 0:
                self._dash = 0.45
            return
        if self._dash > 0:
            self._dash -= dt
            self._pos += self._dash_dir * self._speed * 4.2 * speed_mult * dt
            return
        super().behave(dt, world, speed_mult)
        self._dash_timer -= dt
        offset = world.player.pos - self._pos
        if self._dash_timer <= 0 and 0 < offset.length() < 420:
            self._dash_timer = 4.5
            self._windup = 0.6
            self._dash_dir = offset.normalize()

    def on_death(self, world):
        world.drop_xp(self._pos, self.xp, 5)
        if world.rng.random() < 0.35:
            world.spawn_pickup(HealOrb(self._pos))


BOSS_NAMES = ("Primordial Golem", "Storm Hydra", "Cinder Leviathan",
              "Glacial Titan", "Void Elemental")


class BossEnemy(Enemy):
    """Appears every 5 minutes. Cycles through several attack patterns."""
    kind = "boss"
    shape = "boss"
    color = (200, 60, 255)
    base_hp = 2400
    base_speed = 78
    base_damage = 26
    radius = 54
    xp = 120
    mass = 40.0
    knockback_resist = 0.97
    is_boss = True
    PATTERNS = ("chase", "nova", "charge", "summon", "spiral")

    def __init__(self, pos, index, hp_mult=1.0, speed_mult=1.0, dmg_mult=1.0):
        super().__init__(pos, hp_mult * (1 + 0.9 * index), speed_mult, dmg_mult)
        self._index = index
        self._name = BOSS_NAMES[index % len(BOSS_NAMES)]
        self._pattern = "chase"
        self._pattern_timer = 3.0
        self._pattern_step = 0
        self._sub_timer = 0.0
        self._windup = 0.0
        self._dash_dir = Vector2(1, 0)
        self._spiral_angle = 0.0

    @property
    def name(self):
        return self._name

    @property
    def pattern(self):
        return self._pattern

    @property
    def enraged(self):
        return self.hp_ratio < 0.5

    def is_telegraphing(self):
        return self._windup > 0

    def _next_pattern(self, world):
        self._pattern_step += 1
        choices = list(self.PATTERNS[1:])
        self._pattern = world.rng.choice(choices) if self._pattern == "chase" else "chase"
        self._pattern_timer = {"chase": 2.6, "nova": 2.0, "charge": 2.4,
                               "summon": 1.2, "spiral": 3.0}[self._pattern]
        if self.enraged:
            self._pattern_timer *= 0.75
        self._sub_timer = 0.0
        if self._pattern == "charge":
            self._windup = 0.8
            self._dash_dir = (world.player.pos - self._pos)
            if self._dash_dir.length_squared() > 0:
                self._dash_dir = self._dash_dir.normalize()
            else:
                self._dash_dir = Vector2(1, 0)
        elif self._pattern == "summon":
            for i in range(6 + self._index * 2):
                angle = math.tau * i / (6 + self._index * 2)
                spawn = self._pos + Vector2(math.cos(angle), math.sin(angle)) * 110
                world.add_enemy(FastEnemy(spawn, 1 + self._index, 1.0, 1.0))
            world.events.push("text", self._pos, color=self.color, text="SUMMON!")

    def behave(self, dt, world, speed_mult):
        player_pos = world.player.pos
        if (player_pos - self._pos).length_squared() > 650 * 650:
            # never let the player simply outrun the fight
            self._move_towards(player_pos, self._speed * 3.2, dt)
            return
        self._pattern_timer -= dt
        if self._pattern_timer <= 0:
            self._next_pattern(world)
        rage = 1.35 if self.enraged else 1.0
        if self._pattern == "chase":
            self._move_towards(player_pos, self._speed * speed_mult * rage, dt)
        elif self._pattern == "nova":
            self._sub_timer -= dt
            if self._sub_timer <= 0:
                self._sub_timer = 0.7 / rage
                count = 18 if self.enraged else 14
                offset = world.rng.random() * math.tau
                for i in range(count):
                    angle = offset + math.tau * i / count
                    vel = Vector2(math.cos(angle), math.sin(angle)) * 210
                    world.spawn_enemy_bullet(self._pos, vel, self._damage * 0.6, 9, self.color)
                world.events.push("shake", self._pos, value=4)
        elif self._pattern == "charge":
            if self._windup > 0:
                self._windup -= dt
            else:
                self._pos += self._dash_dir * self._speed * 6.0 * rage * dt
        elif self._pattern == "spiral":
            self._move_towards(player_pos, self._speed * 0.4 * speed_mult, dt)
            self._sub_timer -= dt
            if self._sub_timer <= 0:
                self._sub_timer = 0.09 / rage
                self._spiral_angle += 0.42
                for arm in range(3):
                    angle = self._spiral_angle + arm * math.tau / 3
                    vel = Vector2(math.cos(angle), math.sin(angle)) * 190
                    world.spawn_enemy_bullet(self._pos, vel, self._damage * 0.5, 7, (255, 120, 220))

    def on_death(self, world):
        world.drop_xp(self._pos, self.xp, 12)
        world.spawn_pickup(ElementalCore(self._pos))
        world.events.push("boss_defeated", self._pos, color=self.color, text=self._name, big=True)


class WaveDirector:
    """Decides what spawns, where and when, scaling difficulty smoothly."""

    # (enemy class, minute at which it starts appearing, base weight)
    ROSTER = (
        (BasicEnemy, 0.0, 100),
        (FastEnemy, 0.75, 45),
        (RangedEnemy, 1.5, 22),
        (TankEnemy, 2.5, 18),
    )

    def __init__(self):
        self._spawn_budget = 0.0
        self._next_boss = BOSS_INTERVAL
        self._bosses_spawned = 0
        self._warned = False
        self._next_swarm = 75.0

    @property
    def bosses_spawned(self):
        return self._bosses_spawned

    @property
    def time_to_boss(self):
        return self._next_boss

    # -- difficulty curves (all smooth, no sudden spikes) ----------------
    @staticmethod
    def hp_multiplier(t):
        return 1.0 + t / 85.0 * 0.5 + (t / 300.0) ** 2 * 0.9

    @staticmethod
    def speed_multiplier(t):
        return 1.0 + min(t / 900.0, 0.35)

    @staticmethod
    def damage_multiplier(t):
        return 1.0 + t / 300.0 * 0.35

    @staticmethod
    def spawn_rate(t):
        """Enemies per second."""
        return 1.2 + 0.05 * t ** 0.88

    def update(self, dt, world):
        t = world.time
        boss_alive = world.boss is not None
        # --- boss timing -------------------------------------------------
        if not self._warned and t >= self._next_boss - BOSS_WARNING_TIME:
            self._warned = True
            world.events.push("boss_warning", world.player.pos, text="A BOSS APPROACHES")
        if t >= self._next_boss:
            self._spawn_boss(world)
            self._next_boss += BOSS_INTERVAL
            self._warned = False
        # --- swarm events: a ring of enemies closes in -------------------
        if t >= self._next_swarm and not boss_alive:
            self._next_swarm += 60.0
            self._spawn_swarm(world)
        # --- regular trickle ---------------------------------------------
        rate = self.spawn_rate(t) * (0.45 if boss_alive else 1.0)
        self._spawn_budget += rate * dt
        while self._spawn_budget >= 1.0:
            self._spawn_budget -= 1.0
            if world.enemy_count() >= MAX_ENEMIES:
                self._spawn_budget = 0.0
                break
            self._spawn_one(world)

    def _ring_position(self, world, distance=None):
        angle = world.rng.random() * math.tau
        if distance is None:
            distance = world.rng.uniform(SPAWN_RING_MIN, SPAWN_RING_MAX)
        pos = world.player.pos + Vector2(math.cos(angle), math.sin(angle)) * distance
        pos.x = min(max(pos.x, 10), ARENA_SIZE - 10)
        pos.y = min(max(pos.y, 10), ARENA_SIZE - 10)
        return pos

    def _choose_class(self, world, t):
        minutes = t / 60.0
        options = []
        for cls, start, weight in self.ROSTER:
            if minutes >= start:
                # newly unlocked types ramp up instead of appearing all at once
                ramp = min(1.0, (minutes - start) / 1.5 + 0.25)
                options.append((cls, weight * ramp))
        total = sum(w for _, w in options)
        roll = world.rng.random() * total
        for cls, weight in options:
            roll -= weight
            if roll <= 0:
                return cls
        return BasicEnemy

    def _spawn_one(self, world):
        t = world.time
        hp, spd, dmg = self.hp_multiplier(t), self.speed_multiplier(t), self.damage_multiplier(t)
        elite_chance = 0.0 if t < 150 else min(0.03, 0.006 + (t - 150) / 20000)
        if world.rng.random() < elite_chance:
            cls = EliteEnemy
        else:
            cls = self._choose_class(world, t)
        world.add_enemy(cls(self._ring_position(world), hp, spd, dmg))

    def _spawn_swarm(self, world):
        t = world.time
        count = min(40, 16 + int(t / 30))
        hp = self.hp_multiplier(t) * 0.8
        for i in range(count):
            angle = math.tau * i / count
            pos = world.player.pos + Vector2(math.cos(angle), math.sin(angle)) * 640
            pos.x = min(max(pos.x, 10), ARENA_SIZE - 10)
            pos.y = min(max(pos.y, 10), ARENA_SIZE - 10)
            world.add_enemy(BasicEnemy(pos, hp, 1.0, self.damage_multiplier(t)))
        world.events.push("text", world.player.pos, color=(255, 120, 140), text="SURROUNDED!")

    def _spawn_boss(self, world):
        t = world.time
        boss = BossEnemy(self._ring_position(world, 600), self._bosses_spawned,
                         self.hp_multiplier(t) * 0.55, 1.0, self.damage_multiplier(t))
        self._bosses_spawned += 1
        world.add_enemy(boss)
        world.events.push("boss_spawn", boss.pos, color=boss.color, text=boss.name, big=True)
