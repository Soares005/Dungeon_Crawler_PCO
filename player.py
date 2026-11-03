"""The player character and its stats."""
from pygame.math import Vector2

from settings import (ARENA_SIZE, PLAYER_RADIUS, PLAYER_BASE_HP, PLAYER_BASE_SPEED,
                      PLAYER_PICKUP_RADIUS, PLAYER_IFRAMES, MAX_EXTRA_PROJECTILES)
from elements import create_element


class PlayerStats:
    """All the numbers that basic upgrades modify. Only improve() changes them."""

    STAT_NAMES = ("damage", "move_speed", "attack_speed", "projectile_size",
                  "extra_projectiles", "pickup_radius", "max_hp", "regen")

    def __init__(self):
        self._damage_mult = 1.0
        self._move_speed = float(PLAYER_BASE_SPEED)
        self._attack_speed = 1.0
        self._projectile_size = 1.0
        self._extra_projectiles = 0
        self._pickup_radius = float(PLAYER_PICKUP_RADIUS)
        self._max_hp = float(PLAYER_BASE_HP)
        self._regen = 0.0

    @property
    def damage_mult(self):
        return self._damage_mult

    @property
    def move_speed(self):
        return self._move_speed

    @property
    def attack_speed(self):
        return self._attack_speed

    @property
    def projectile_size(self):
        return self._projectile_size

    @property
    def extra_projectiles(self):
        return self._extra_projectiles

    @property
    def pickup_radius(self):
        return self._pickup_radius

    @property
    def max_hp(self):
        return self._max_hp

    @property
    def regen(self):
        return self._regen

    def can_improve(self, stat):
        if stat == "extra_projectiles":
            return self._extra_projectiles < MAX_EXTRA_PROJECTILES
        if stat == "move_speed":
            return self._move_speed < PLAYER_BASE_SPEED * 2
        if stat == "attack_speed":
            return self._attack_speed < 3.0
        return stat in self.STAT_NAMES

    def improve(self, stat, amount):
        """Apply a stat upgrade. Percent stats take fractions (0.2 = +20%)."""
        if stat == "damage":
            self._damage_mult += amount
        elif stat == "move_speed":
            self._move_speed = min(PLAYER_BASE_SPEED * 2, self._move_speed + PLAYER_BASE_SPEED * amount)
        elif stat == "attack_speed":
            self._attack_speed = min(3.0, self._attack_speed + amount)
        elif stat == "projectile_size":
            self._projectile_size += amount
        elif stat == "extra_projectiles":
            self._extra_projectiles = min(MAX_EXTRA_PROJECTILES, self._extra_projectiles + int(amount))
        elif stat == "pickup_radius":
            self._pickup_radius += PLAYER_PICKUP_RADIUS * amount
        elif stat == "max_hp":
            self._max_hp += amount
        elif stat == "regen":
            self._regen += amount
        else:
            raise ValueError(f"Unknown stat: {stat!r}")


class Player:
    radius = PLAYER_RADIUS

    def __init__(self, pos, starting_element):
        self._pos = Vector2(pos)
        self._facing = Vector2(1, 0)
        self._moving = False
        self._stats = PlayerStats()
        self._hp = self._stats.max_hp
        self._iframes = 0.0
        self._hurt_flash = 0.0
        self._level = 1
        self._xp = 0
        self._elements = {}          # element_id -> Element
        self._fusions = {}           # fusion_id -> Fusion
        self.add_element(starting_element)

    # -- read-only -----------------------------------------------------------
    @property
    def pos(self):
        return Vector2(self._pos)

    @property
    def facing(self):
        return Vector2(self._facing)

    @property
    def moving(self):
        return self._moving

    @property
    def stats(self):
        return self._stats

    @property
    def hp(self):
        return self._hp

    @property
    def alive(self):
        return self._hp > 0

    @property
    def invulnerable(self):
        return self._iframes > 0

    @property
    def hurt_flash(self):
        return self._hurt_flash

    @property
    def level(self):
        return self._level

    @property
    def xp(self):
        return self._xp

    @property
    def xp_to_next(self):
        n = self._level - 1
        return int(4 + n * 5 + n ** 1.55)

    @property
    def elements(self):
        return tuple(self._elements.values())

    @property
    def fusions(self):
        return tuple(self._fusions.values())

    # -- elements & fusions ------------------------------------------------------
    def has_element(self, element_id):
        return element_id in self._elements

    def get_element(self, element_id):
        return self._elements.get(element_id)

    def add_element(self, element_id, level=1):
        if element_id in self._elements:
            return self._elements[element_id]
        element = create_element(element_id, level)
        self._elements[element_id] = element
        return element

    def has_fusion(self, fusion_id):
        return fusion_id in self._fusions

    def get_fusion(self, fusion_id):
        return self._fusions.get(fusion_id)

    def add_fusion(self, recipe):
        if recipe.fusion_id not in self._fusions:
            self._fusions[recipe.fusion_id] = recipe.create()
        return self._fusions[recipe.fusion_id]

    # -- health & xp --------------------------------------------------------------
    def take_damage(self, amount):
        """Returns True if the hit landed (False while invulnerable)."""
        if self._iframes > 0 or amount <= 0 or not self.alive:
            return False
        self._hp = max(0.0, self._hp - amount)
        self._iframes = PLAYER_IFRAMES
        self._hurt_flash = 0.25
        return True

    def heal(self, amount):
        self._hp = min(self._stats.max_hp, self._hp + max(0.0, amount))

    def improve_stat(self, stat, amount):
        self._stats.improve(stat, amount)
        if stat == "max_hp":
            self.heal(amount)

    def add_xp(self, amount):
        """Add experience. Returns how many levels were gained."""
        self._xp += max(0, int(amount))
        gained = 0
        while self._xp >= self.xp_to_next:
            self._xp -= self.xp_to_next
            self._level += 1
            gained += 1
        return gained

    # -- per frame ----------------------------------------------------------------
    def move(self, direction, dt):
        direction = Vector2(direction)
        self._moving = direction.length_squared() > 0
        if self._moving:
            direction = direction.normalize()
            self._facing = direction
            self._pos += direction * self._stats.move_speed * dt
            self._pos.x = min(max(self._pos.x, self.radius), ARENA_SIZE - self.radius)
            self._pos.y = min(max(self._pos.y, self.radius), ARENA_SIZE - self.radius)

    def update(self, dt, world):
        if self._iframes > 0:
            self._iframes -= dt
        if self._hurt_flash > 0:
            self._hurt_flash -= dt
        if self._stats.regen > 0:
            self.heal(self._stats.regen * dt)
        for element in self.elements:
            element.update(dt, world, self)
        for fusion in self.fusions:
            fusion.update(dt, world, self)
