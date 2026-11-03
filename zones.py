"""Area effects (zones) that live in the world for a while: tornadoes, storms,
steam clouds, meteors, spikes...

AreaEffect is the base class with a template update(): it ages the effect,
lets the subclass move() it, and calls on_tick() at a fixed interval.
Subclasses override those hooks to create completely different abilities.
"""
import math
from abc import ABC

from pygame.math import Vector2

from settings import ELEMENT_COLORS, FIRE, WATER, LIGHTNING, ICE, EARTH, WIND
from status import Burning, Wet, Slowed, Electrified


class AreaEffect(ABC):
    kind = "zone"
    layer = "under"          # drawn below ("under") or above ("over") enemies

    def __init__(self, pos, radius, duration, damage, element, tick_interval=0.3):
        self._pos = Vector2(pos)
        self._radius = float(radius)
        self._duration = float(duration)
        self._damage = float(damage)
        self._element = element
        self._tick_interval = tick_interval
        self._tick_timer = 0.0
        self._age = 0.0
        self._alive = True

    # -- read-only -----------------------------------------------------------
    @property
    def pos(self):
        return Vector2(self._pos)

    @property
    def radius(self):
        return self._radius

    @property
    def age(self):
        return self._age

    @property
    def duration(self):
        return self._duration

    @property
    def progress(self):
        return min(1.0, self._age / self._duration) if self._duration > 0 else 1.0

    @property
    def alive(self):
        return self._alive

    @property
    def color(self):
        return ELEMENT_COLORS.get(self._element, (255, 255, 255))

    # -- template method -------------------------------------------------------
    def update(self, dt, world):
        self._age += dt
        self.move(dt, world)
        self._tick_timer -= dt
        if self._tick_timer <= 0:
            self._tick_timer += self._tick_interval
            self.on_tick(world)
        if self._age >= self._duration:
            self._alive = False
            self.on_end(world)

    def move(self, dt, world):
        pass

    def on_tick(self, world):
        for enemy in world.enemies_in_radius(self._pos, self._radius):
            world.damage_enemy(enemy, self._damage, self._element)
            if enemy.alive:
                self.affect(enemy, world)

    def affect(self, enemy, world):
        pass

    def on_end(self, world):
        pass


class SteamCloud(AreaEffect):
    """Created by the Steam Burst reaction and the Steam Explosion fusion."""
    kind = "steam"
    layer = "over"

    def __init__(self, pos, radius, duration, damage):
        super().__init__(pos, radius, duration, damage, WATER, tick_interval=0.35)

    @property
    def color(self):
        return (225, 235, 245)

    def affect(self, enemy, world):
        enemy.apply_status(Wet(2.0))


class FireTornado(AreaEffect):
    kind = "tornado"
    layer = "over"

    def __init__(self, pos, direction, radius, duration, damage, burn_dps):
        super().__init__(pos, radius, duration, damage, FIRE, tick_interval=0.2)
        self._vel = Vector2(direction) * 170
        self._burn_dps = burn_dps

    def move(self, dt, world):
        target = world.nearest_enemy(self._pos, 300)
        if target is not None:
            desired = target.pos - self._pos
            if desired.length_squared() > 1:
                desired.scale_to_length(200)
                self._vel += (desired - self._vel) * min(1.0, 2.0 * dt)
        self._pos += self._vel * dt
        # tornadoes suck enemies toward their eye
        for enemy in world.enemies_in_radius(self._pos, self._radius * 1.3):
            enemy.pull_towards(self._pos, 120, dt)

    def affect(self, enemy, world):
        enemy.apply_status(Burning(2.5, self._burn_dps))


class Meteor(AreaEffect):
    """Falls for a moment (shadow grows), then impacts and leaves a burning crater."""
    kind = "meteor"
    layer = "over"
    FALL_TIME = 0.75

    def __init__(self, pos, radius, damage, delay=0.0):
        super().__init__(pos, radius, self.FALL_TIME + delay + 1.4, damage * 0.08, FIRE,
                         tick_interval=0.3)
        self._impact_damage = damage
        self._delay = delay
        self._impacted = False

    @property
    def impacted(self):
        return self._impacted

    @property
    def fall_progress(self):
        return min(1.0, max(0.0, (self._age - self._delay) / self.FALL_TIME))

    def update(self, dt, world):
        super().update(dt, world)
        if not self._impacted and self._age >= self._delay + self.FALL_TIME:
            self._impacted = True
            burn = self._impact_damage * 0.12
            world.explode(self._pos, self._radius, self._impact_damage, FIRE,
                          on_each=lambda e: e.apply_status(Burning(3.0, burn)),
                          knock_force=320, shake=7, color=(255, 140, 50))

    def on_tick(self, world):
        if self._impacted:     # burning crater after the impact
            for enemy in world.enemies_in_radius(self._pos, self._radius * 0.6):
                world.damage_enemy(enemy, self._damage, FIRE, allow_reactions=False)


class ElectricStormAura(AreaEffect):
    """Rain soaks enemies around the player; wet enemies conduct arcs between each other."""
    kind = "electric_storm"
    layer = "over"

    def __init__(self, pos, radius, duration, damage, links):
        super().__init__(pos, radius, duration, damage, LIGHTNING, tick_interval=0.45)
        self._links = links

    def move(self, dt, world):
        self._pos = world.player.pos

    def on_tick(self, world):
        enemies = world.enemies_in_radius(self._pos, self._radius)
        for enemy in enemies:
            enemy.apply_status(Wet(2.5))
        wet = [e for e in enemies if e.has_status("wet")]
        if not wet:
            return
        world.rng.shuffle(wet)
        # build a conduction network: each wet enemy links to its nearest unlinked neighbour
        current = wet.pop()
        chain = [current]
        while wet and len(chain) < self._links:
            nxt = min(wet, key=lambda e: (e.pos - current.pos).length_squared())
            wet.remove(nxt)
            chain.append(nxt)
            current = nxt
        points = [tuple(e.pos) for e in chain]
        for enemy in chain:
            world.damage_enemy(enemy, self._damage, LIGHTNING, allow_reactions=False)
            if enemy.alive:
                enemy.apply_status(Electrified(2.0, self._damage * 0.15))
        world.events.push("lightning", self._pos, color=(140, 220, 255), points=points, value=3)


class BlizzardAura(AreaEffect):
    kind = "blizzard"
    layer = "over"

    def __init__(self, pos, radius, duration, damage):
        super().__init__(pos, radius, duration, damage, ICE, tick_interval=0.3)

    def move(self, dt, world):
        self._pos = world.player.pos

    def affect(self, enemy, world):
        if enemy.add_chill(1, 0.55, 1.5, 1.6):
            world.events.push("freeze", enemy.pos, color=ELEMENT_COLORS[ICE])


class MagneticField(AreaEffect):
    """Pulls enemies together, then discharges in a big electric burst."""
    kind = "magnet_field"
    layer = "under"

    def __init__(self, pos, radius, duration, damage):
        super().__init__(pos, radius, duration, damage * 0.06, EARTH, tick_interval=0.4)
        self._burst = damage

    def move(self, dt, world):
        for enemy in world.enemies_in_radius(self._pos, self._radius * 1.15):
            enemy.pull_towards(self._pos, 240, dt)

    def on_end(self, world):
        hit = world.explode(self._pos, self._radius * 0.75, self._burst, LIGHTNING,
                            on_each=lambda e: e.apply_status(Electrified(2.5, self._burst * 0.05)),
                            shake=6, color=ELEMENT_COLORS[LIGHTNING])
        center = tuple(self._pos)
        for enemy in hit[:12]:
            world.events.push("lightning", center, color=ELEMENT_COLORS[LIGHTNING],
                              points=[center, tuple(enemy.pos)], value=2)


class Sandstorm(AreaEffect):
    kind = "sandstorm"
    layer = "over"

    def __init__(self, pos, direction, radius, duration, damage):
        super().__init__(pos, radius, duration, damage, EARTH, tick_interval=0.25)
        self._vel = Vector2(direction) * 120
        self._turn = 0.6

    def move(self, dt, world):
        self._vel.rotate_ip(math.degrees(self._turn * dt))
        self._pos += self._vel * dt

    def affect(self, enemy, world):
        enemy.apply_status(Slowed(1.0, 0.45))
        enemy.knockback(self._vel, 40)


class CrystalSpike(AreaEffect):
    """Erupts from the ground after a short delay, impaling whatever stands on it."""
    kind = "crystal_spike"
    layer = "over"

    def __init__(self, pos, radius, damage, delay):
        super().__init__(pos, radius, delay + 0.55, damage, ICE, tick_interval=999)
        self._delay = delay
        self._erupted = False
        self._tick_timer = 999

    @property
    def erupted(self):
        return self._erupted

    @property
    def rise(self):
        """0..1 height of the spike for the renderer."""
        if not self._erupted:
            return 0.0
        t = self._age - self._delay
        return min(1.0, t / 0.08) * (1.0 - max(0.0, (t - 0.35) / 0.2))

    def update(self, dt, world):
        super().update(dt, world)
        if not self._erupted and self._age >= self._delay:
            self._erupted = True
            for enemy in world.enemies_in_radius(self._pos, self._radius):
                world.damage_enemy(enemy, self._damage, EARTH)
                if enemy.alive and enemy.add_chill(2, 0.5, 1.8, 1.3):
                    world.events.push("freeze", enemy.pos, color=ELEMENT_COLORS[ICE])
            world.events.push("spike", self._pos, color=ELEMENT_COLORS[ICE])


class ThunderCloud(AreaEffect):
    """A drifting storm cloud that rains lightning strikes inside its area."""
    kind = "thunderstorm"
    layer = "over"

    def __init__(self, pos, radius, duration, damage, strike_interval):
        super().__init__(pos, radius, duration, damage, LIGHTNING, tick_interval=strike_interval)
        self._wander = Vector2(1, 0)

    def move(self, dt, world):
        # drift around the player, a bit ahead of them
        self._wander.rotate_ip(40 * dt)
        target = world.player.pos + self._wander * 120
        self._pos += (target - self._pos) * min(1.0, 1.4 * dt)

    def on_tick(self, world):
        candidates = world.enemies_in_radius(self._pos, self._radius)
        if candidates and world.rng.random() < 0.8:
            point = world.rng.choice(candidates).pos
        else:
            angle = world.rng.random() * math.tau
            dist = world.rng.random() * self._radius
            point = self._pos + Vector2(math.cos(angle), math.sin(angle)) * dist
        world.explode(point, 48, self._damage, LIGHTNING,
                      on_each=lambda e: e.apply_status(Electrified(1.5, self._damage * 0.08)),
                      quiet=True)
        sky = (point.x + world.rng.uniform(-30, 30), point.y - 260)
        world.events.push("lightning", point, color=(220, 230, 255),
                          points=[sky, tuple(point)], value=3, big=True)
        world.events.push("explosion", point, color=ELEMENT_COLORS[LIGHTNING], value=48)
