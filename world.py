"""The World: one run of the game, with all of its objects and rules.

This is the heart of the logic layer. It owns the collections of objects
(enemies, projectiles, zones, pickups), moves time forward, resolves
collisions and damage, and reports what happened through the event queue.
It never draws anything - see renderer.py for that.
"""
import random

from pygame.math import Vector2

from settings import ARENA_SIZE, ELEMENT_COLORS, LIGHTNING, MAX_GEMS
from events import EventQueue
from spatial import SpatialGrid
from player import Player
from enemies import WaveDirector
from projectiles import EnemyBullet
from pickups import XPGem
from reactions import ReactionSystem
from fusions import eligible_recipes

RELOCATE_DISTANCE = 1500
SEPARATION_CELL = 48


class World:
    def __init__(self, starting_element, known_fusions=(), known_reactions=(), seed=None):
        self._rng = random.Random(seed)
        self._player = Player((ARENA_SIZE / 2, ARENA_SIZE / 2), starting_element)
        self._enemies = []
        self._spawn_queue = []
        self._projectiles = []
        self._enemy_bullets = []
        self._effects = []
        self._pickups = []
        self._grid = SpatialGrid()
        self._director = WaveDirector()
        self._reactions = ReactionSystem()
        self._events = EventQueue()
        self._time = 0.0
        self._kills = 0
        self._bosses_defeated = 0
        self._bosses = []
        self._pending_levels = 0
        self._pending_rewards = 0
        self._game_over = False
        # discovery tracking (persisted by the SaveManager through the game states)
        self._known_fusions = set(known_fusions)
        self._known_reactions = set(known_reactions)
        self._new_discoveries = []
        self._run_fusions = []
        self._reaction_counts = {}
        self._damage_by_element = {}

    # ------------------------------------------------------------------
    # Read-only access
    # ------------------------------------------------------------------
    @property
    def rng(self):
        return self._rng

    @property
    def events(self):
        return self._events

    @property
    def player(self):
        return self._player

    @property
    def enemies(self):
        return tuple(self._enemies)

    @property
    def projectiles(self):
        return tuple(self._projectiles)

    @property
    def enemy_bullets(self):
        return tuple(self._enemy_bullets)

    @property
    def effects(self):
        return tuple(self._effects)

    @property
    def pickups(self):
        return tuple(self._pickups)

    @property
    def time(self):
        return self._time

    @property
    def kills(self):
        return self._kills

    @property
    def boss(self):
        """The oldest living boss (None if there is none)."""
        return self._bosses[0] if self._bosses else None

    @property
    def director(self):
        return self._director

    @property
    def pending_level_ups(self):
        return self._pending_levels

    @property
    def pending_rewards(self):
        return self._pending_rewards

    @property
    def game_over(self):
        return self._game_over

    def enemy_count(self):
        return len(self._enemies) + len(self._spawn_queue)

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------
    def update(self, dt, move_direction):
        if self._game_over:
            return
        self._time += dt
        player = self._player
        player.move(move_direction, dt)

        self._director.update(dt, self)
        self._flush_spawns()

        self._grid.rebuild(self._enemies)
        for enemy in self._enemies:
            enemy.update(dt, self)
        self._separate_enemies()
        self._relocate_stragglers()
        self._grid.rebuild(self._enemies)

        player.update(dt, self)
        self._update_projectiles(dt)
        for effect in self._effects:
            effect.update(dt, self)
        self._update_enemy_bullets(dt)
        self._contact_damage()
        self._update_pickups(dt)
        self._flush_spawns()
        self._cleanup()

        if not player.alive:
            self._game_over = True
            self._events.push("player_death", player.pos, color=(255, 255, 255), big=True)

    def _flush_spawns(self):
        if self._spawn_queue:
            self._enemies.extend(self._spawn_queue)
            self._spawn_queue.clear()

    def _separate_enemies(self):
        """Push overlapping enemies apart so the horde never collapses into one blob.

        Performance matters here (hundreds of enemies, every frame), so this
        uses plain floats and its own fine grid (cell = 48 px, larger than any
        two normal enemy radii together) and checks at most a few neighbours.
        """
        cell = SEPARATION_CELL
        data = []
        buckets = {}
        for enemy in self._enemies:
            if enemy.alive and not enemy.is_boss:
                pos = enemy.pos
                entry = (enemy, pos.x, pos.y, enemy.radius, enemy.mass)
                data.append(entry)
                key = (int(pos.x // cell), int(pos.y // cell))
                bucket = buckets.get(key)
                if bucket is None:
                    buckets[key] = [entry]
                else:
                    bucket.append(entry)
        for enemy, x, y, r, _ in data:
            cx, cy = int(x // cell), int(y // cell)
            px = py = 0.0
            checked = 0
            for nx in (cx - 1, cx, cx + 1):
                for ny in (cy - 1, cy, cy + 1):
                    bucket = buckets.get((nx, ny))
                    if not bucket:
                        continue
                    for other, ox, oy, orad, omass in bucket:
                        if other is enemy:
                            continue
                        dx, dy = x - ox, y - oy
                        min_dist = r + orad
                        dist_sq = dx * dx + dy * dy
                        if dist_sq < min_dist * min_dist:
                            if dist_sq == 0:
                                dx, dy, dist_sq = self._rng.uniform(-1, 1), 1.0, 1.0
                            dist = dist_sq ** 0.5
                            strength = (min_dist - dist) / dist * 0.35 * min(2.0, omass)
                            px += dx * strength
                            py += dy * strength
                        checked += 1
                        if checked >= 10:
                            break
            if px or py:
                enemy.push(Vector2(px, py))
        # bosses shove small enemies out of their way
        for boss in self._bosses:
            bpos = boss.pos
            for enemy in self.enemies_in_radius(bpos, boss.radius):
                if enemy is not boss:
                    offset = enemy.pos - bpos
                    if offset.length_squared() > 0:
                        enemy.push(offset.normalize() * 6 * enemy.mass)

    def _relocate_stragglers(self):
        """Enemies left far behind are moved back in front of the player."""
        player_pos = self._player.pos
        limit = RELOCATE_DISTANCE * RELOCATE_DISTANCE
        for enemy in self._enemies:
            if not enemy.is_boss and (enemy.pos - player_pos).length_squared() > limit:
                direction = self._player.facing
                spot = player_pos + direction.rotate(self._rng.uniform(-60, 60)) * 760
                spot.x = min(max(spot.x, 10), ARENA_SIZE - 10)
                spot.y = min(max(spot.y, 10), ARENA_SIZE - 10)
                enemy.relocate(spot)

    def _update_projectiles(self, dt):
        for projectile in self._projectiles:
            projectile.update(dt)
            if not projectile.alive:
                continue
            ppos = projectile.pos
            for enemy in self._grid.query(ppos, projectile.radius):
                if not enemy.alive or not projectile.can_hit(enemy):
                    continue
                reach = projectile.radius + enemy.radius
                if (enemy.pos - ppos).length_squared() < reach * reach:
                    projectile.hit(enemy, self)
                    self._events.push("impact", ppos, color=projectile.color)
                    if not projectile.alive:
                        break

    def _update_enemy_bullets(self, dt):
        player = self._player
        for bullet in self._enemy_bullets:
            bullet.update(dt)
            if bullet.alive:
                reach = bullet.radius + player.radius
                if (bullet.pos - player.pos).length_squared() < reach * reach:
                    bullet.on_hit_player(player, self)

    def _contact_damage(self):
        player = self._player
        if player.invulnerable:
            return
        ppos = player.pos
        for enemy in self._grid.query(ppos, player.radius):
            if not enemy.can_hit_player():
                continue
            reach = enemy.radius + player.radius
            offset = enemy.pos - ppos
            if offset.length_squared() < reach * reach:
                if player.take_damage(enemy.contact_damage):
                    self._events.push("player_hurt", ppos, value=enemy.contact_damage)
                    enemy.knockback(offset if offset.length_squared() > 0 else Vector2(1, 0), 260)
                break

    def _update_pickups(self, dt):
        player = self._player
        for pickup in self._pickups:
            if pickup.update(dt, player):
                pickup.collect(player, self)

    def _cleanup(self):
        self._enemies = [e for e in self._enemies if e.alive]
        self._projectiles = [p for p in self._projectiles if p.alive]
        self._enemy_bullets = [b for b in self._enemy_bullets if b.alive]
        self._effects = [z for z in self._effects if z.alive]
        self._pickups = [p for p in self._pickups if not p.collected]

    # ------------------------------------------------------------------
    # Queries used by elements, fusions and enemies
    # ------------------------------------------------------------------
    def enemies_in_radius(self, pos, radius):
        pos = Vector2(pos)
        found = []
        for enemy in self._grid.query(pos, radius):
            if enemy.alive:
                reach = radius + enemy.radius
                if (enemy.pos - pos).length_squared() < reach * reach:
                    found.append(enemy)
        return found

    def nearest_enemy(self, pos, max_range):
        pos = Vector2(pos)
        best, best_dist = None, max_range * max_range
        for enemy in self._grid.query(pos, max_range):
            if enemy.alive:
                dist = (enemy.pos - pos).length_squared()
                if dist < best_dist:
                    best, best_dist = enemy, dist
        return best

    def random_enemy_in_range(self, pos, max_range, exclude=()):
        candidates = [e for e in self.enemies_in_radius(pos, max_range) if id(e) not in exclude]
        return self._rng.choice(candidates) if candidates else None

    def densest_point(self, origin, radius, avoid=()):
        """Position of the enemy with the most neighbours (good AoE target)."""
        candidates = self.enemies_in_radius(origin, radius)
        if not candidates:
            return None
        if len(candidates) > 20:
            candidates = self._rng.sample(candidates, 20)
        best, best_score = None, -1
        for enemy in candidates:
            pos = enemy.pos
            if any((pos - Vector2(a)).length_squared() < 140 * 140 for a in avoid):
                continue
            score = len(self.enemies_in_radius(pos, 110))
            if score > best_score:
                best, best_score = pos, score
        return best

    # ------------------------------------------------------------------
    # Spawning
    # ------------------------------------------------------------------
    def add_enemy(self, enemy):
        self._spawn_queue.append(enemy)
        if enemy.is_boss:
            self._bosses.append(enemy)

    def spawn_projectile(self, projectile):
        self._projectiles.append(projectile)

    def spawn_enemy_bullet(self, pos, vel, damage, radius, color):
        self._enemy_bullets.append(EnemyBullet(pos, vel, damage, radius, color))

    def spawn_effect(self, effect):
        self._effects.append(effect)

    def spawn_pickup(self, pickup):
        self._pickups.append(pickup)

    def drop_xp(self, pos, total, pieces):
        pieces = max(1, int(pieces))
        value = max(1, int(round(total / pieces)))
        gems = [p for p in self._pickups if isinstance(p, XPGem)]
        for _ in range(pieces):
            if len(gems) >= MAX_GEMS:
                # too many crystals on the floor: merge into an existing one
                self._rng.choice(gems).absorb(value)
                continue
            offset = Vector2(self._rng.uniform(-14, 14), self._rng.uniform(-14, 14)) if pieces > 1 else Vector2()
            gem = XPGem(Vector2(pos) + offset, value)
            self._pickups.append(gem)
            gems.append(gem)

    # ------------------------------------------------------------------
    # Combat
    # ------------------------------------------------------------------
    def damage_enemy(self, enemy, amount, element, allow_reactions=True, is_dot=False,
                     knock_dir=None, knock_force=0):
        """The single entry point for damaging enemies. Returns damage dealt."""
        if not enemy.alive or amount <= 0:
            return 0.0
        multiplier = 1.0
        if allow_reactions and not is_dot:
            multiplier = self._reactions.process(self, enemy, element, amount)
        dealt = enemy.take_damage(amount * multiplier)
        if knock_dir is not None and knock_force:
            enemy.knockback(Vector2(knock_dir), knock_force)
        self._damage_by_element[element] = self._damage_by_element.get(element, 0.0) + dealt
        self._events.push("hit", enemy.pos, color=ELEMENT_COLORS.get(element, (255, 255, 255)),
                          value=dealt, big=multiplier > 1.01, text="dot" if is_dot else "")
        if not enemy.alive:
            self._on_enemy_killed(enemy)
        return dealt

    def _on_enemy_killed(self, enemy):
        self._kills += 1
        enemy.on_death(self)
        self._events.push("death", enemy.pos, color=enemy.color, value=enemy.radius,
                          big=enemy.is_boss or enemy.is_elite)
        if enemy.is_boss:
            self._bosses = [b for b in self._bosses if b is not enemy]
            self._bosses_defeated += 1

    def explode(self, pos, radius, damage, element, on_each=None, exclude=None, knock_force=0,
                shake=0, color=None, quiet=False, allow_reactions=True):
        """Damage everything in a circle. Returns the list of enemies hit."""
        pos = Vector2(pos)
        hit = []
        for enemy in self.enemies_in_radius(pos, radius):
            if enemy is exclude:
                continue
            self.damage_enemy(enemy, damage, element, allow_reactions=allow_reactions,
                              knock_dir=(enemy.pos - pos) if knock_force else None,
                              knock_force=knock_force)
            if enemy.alive and on_each is not None:
                on_each(enemy)
            hit.append(enemy)
        if not quiet:
            self._events.push("explosion", pos, color=color or ELEMENT_COLORS.get(element, (255, 255, 255)),
                              value=radius)
        if shake:
            self._events.push("shake", pos, value=shake)
        return hit

    def chain_lightning(self, origin, first, damage, jumps, radius, on_hit=None, color=None,
                        allow_reactions=True, origin_enemy=None, prefer_status=None):
        """Lightning that jumps from enemy to enemy.

        `first` is the first target (None = pick the nearest to origin_enemy).
        `jumps` is how many extra enemies it can jump to.
        """
        hit_ids = set()
        if origin_enemy is not None:
            hit_ids.add(id(origin_enemy))
        points = [tuple(Vector2(origin))]
        current = first
        if current is None:
            current = self._next_chain_target(Vector2(origin), radius, hit_ids, prefer_status)
        hits = 0
        max_hits = jumps + (1 if first is not None else 0)
        while current is not None and hits < max_hits:
            hit_ids.add(id(current))
            points.append(tuple(current.pos))
            self.damage_enemy(current, damage * (0.92 ** hits), LIGHTNING,
                              allow_reactions=allow_reactions)
            if current.alive and on_hit is not None:
                on_hit(current)
            hits += 1
            current = self._next_chain_target(current.pos, radius, hit_ids, prefer_status)
        if len(points) > 1:
            self._events.push("lightning", origin, color=color or ELEMENT_COLORS[LIGHTNING],
                              points=points, value=2)
        return hits

    def _next_chain_target(self, pos, radius, hit_ids, prefer_status):
        best, best_score = None, None
        for enemy in self.enemies_in_radius(pos, radius):
            if id(enemy) in hit_ids:
                continue
            score = (enemy.pos - pos).length_squared()
            if prefer_status and enemy.has_status(prefer_status):
                score *= 0.25          # conductive enemies attract the arc
            if best_score is None or score < best_score:
                best, best_score = enemy, score
        return best

    # ------------------------------------------------------------------
    # Progression & discoveries
    # ------------------------------------------------------------------
    def give_xp(self, amount):
        gained = self._player.add_xp(amount)
        if gained:
            self._pending_levels += gained
            self._events.push("level_up", self._player.pos, color=(255, 230, 120), value=gained)

    def consume_level_up(self):
        self._pending_levels = max(0, self._pending_levels - 1)

    def grant_reward_choice(self):
        self._pending_rewards += 1

    def consume_reward(self):
        self._pending_rewards = max(0, self._pending_rewards - 1)

    def magnetize_all_gems(self):
        for pickup in self._pickups:
            if isinstance(pickup, XPGem):
                pickup.magnetize()

    def register_reaction(self, reaction, enemy):
        self._reaction_counts[reaction.reaction_id] = self._reaction_counts.get(reaction.reaction_id, 0) + 1
        self._events.push("reaction", enemy.pos, color=reaction.color, text=reaction.name)
        if reaction.reaction_id not in self._known_reactions:
            self._known_reactions.add(reaction.reaction_id)
            self._new_discoveries.append(("reaction", reaction.reaction_id))
            self._events.push("discovery", enemy.pos, color=reaction.color,
                              text=f"Reaction discovered: {reaction.name}")

    def register_fusion(self, recipe):
        self._run_fusions.append(recipe.fusion_id)
        self._events.push("fusion_unlocked", self._player.pos, color=recipe.color, text=recipe.name, big=True)
        if recipe.fusion_id not in self._known_fusions:
            self._known_fusions.add(recipe.fusion_id)
            self._new_discoveries.append(("fusion", recipe.fusion_id))
            self._events.push("discovery", self._player.pos, color=recipe.color,
                              text=f"Fusion discovered: {recipe.name}")

    def check_fusion_hint(self):
        recipes = eligible_recipes(self._player)
        if recipes:
            self._events.push("text", self._player.pos, color=(255, 230, 140),
                              text="New fusion possible!")

    def drain_discoveries(self):
        found, self._new_discoveries = self._new_discoveries, []
        return found

    def summary(self):
        """Everything the Game Over screen and the save file need."""
        player = self._player
        return {
            "time": self._time,
            "kills": self._kills,
            "level": player.level,
            "elements": [(e.element_id, e.level) for e in player.elements],
            "fusions": list(self._run_fusions),
            "reactions": dict(self._reaction_counts),
            "bosses": self._bosses_defeated,
            "damage": dict(self._damage_by_element),
        }
