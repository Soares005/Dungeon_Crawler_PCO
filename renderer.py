"""Draws the World. Reads game objects, never changes them.

Rendering is kept completely separate from the combat logic: the logic
classes only expose read-only properties (pos, radius, kind, statuses...)
and this module decides what they look like. Every visual is procedural.
"""
import math
import random

import pygame
from pygame.math import Vector2

from gfx import (blit_glow, blit_alpha_circle, scale_color, lerp_color, regular_polygon)
from settings import (ARENA_SIZE, BG_COLOR, BG_GRID, ARENA_EDGE, DARK, ACCENT, WHITE,
                      ELEMENT_COLORS, STATUS_COLORS, SCREEN_W, SCREEN_H)

TILE = 400


class Camera:
    def __init__(self, width=SCREEN_W, height=SCREEN_H):
        self._size = Vector2(width, height)
        self._center = Vector2()
        self._shake = 0.0
        self._shake_offset = Vector2()
        self._shake_enabled = True
        self._rng = random.Random()

    @property
    def offset(self):
        top_left = self._center - self._size / 2 + self._shake_offset
        return (top_left.x, top_left.y)

    @property
    def view_rect(self):
        ox, oy = self.offset
        return pygame.Rect(int(ox) - 80, int(oy) - 80, int(self._size.x) + 160, int(self._size.y) + 160)

    def set_shake_enabled(self, enabled):
        self._shake_enabled = bool(enabled)

    def snap(self, target):
        self._center = Vector2(target)

    def follow(self, target, dt):
        self._center += (Vector2(target) - self._center) * min(1.0, 9.0 * dt)

    def shake(self, amount):
        if self._shake_enabled:
            self._shake = min(16.0, max(self._shake, float(amount)))

    def update(self, dt):
        if self._shake > 0.1:
            self._shake_offset = Vector2(self._rng.uniform(-1, 1), self._rng.uniform(-1, 1)) * self._shake
            self._shake *= max(0.0, 1.0 - 9.0 * dt)
        else:
            self._shake = 0.0
            self._shake_offset = Vector2()

    def to_screen(self, pos):
        ox, oy = self.offset
        return (pos[0] - ox, pos[1] - oy)


def _make_floor_tile():
    tile = pygame.Surface((TILE, TILE))
    tile.fill(BG_COLOR)
    rng = random.Random(42)
    # faint arcane circles inside cells (never crossing the tile edge)
    for _ in range(5):
        cx, cy = rng.randint(60, TILE - 60), rng.randint(60, TILE - 60)
        r = rng.randint(14, 40)
        pygame.draw.circle(tile, scale_color(BG_GRID, 0.85), (cx, cy), r, 1)
        if rng.random() < 0.5:
            pygame.draw.circle(tile, scale_color(BG_GRID, 0.85), (cx, cy), r // 2, 1)
    for _ in range(40):
        x, y = rng.randint(2, TILE - 3), rng.randint(2, TILE - 3)
        tile.set_at((x, y), scale_color(BG_GRID, 1.3))
    for i in range(0, TILE, 80):
        pygame.draw.line(tile, BG_GRID, (i, 0), (i, TILE))
        pygame.draw.line(tile, BG_GRID, (0, i), (TILE, i))
    return tile


class WorldRenderer:
    def __init__(self):
        self._tile = _make_floor_tile()
        self._time = 0.0

    def draw(self, surface, world, camera, effects, dt):
        self._time += dt
        ox, oy = camera.offset
        view = camera.view_rect
        self._draw_floor(surface, ox, oy)
        self._draw_pickups(surface, world, ox, oy, view)
        self._draw_zones(surface, world, ox, oy, "under")
        self._draw_enemies(surface, world, ox, oy, view)
        self._draw_player(surface, world.player, ox, oy)
        self._draw_projectiles(surface, world, ox, oy, view)
        self._draw_zones(surface, world, ox, oy, "over")
        effects.draw_world_effects(surface, camera)

    # ------------------------------------------------------------------
    def _draw_floor(self, surface, ox, oy):
        surface.fill(DARK)
        arena = pygame.Rect(int(-ox), int(-oy), ARENA_SIZE, ARENA_SIZE)
        surface.set_clip(arena.clip(surface.get_rect()))
        start_x = int(math.floor(ox / TILE) * TILE)
        start_y = int(math.floor(oy / TILE) * TILE)
        width, height = surface.get_size()
        for x in range(start_x, int(ox) + width + TILE, TILE):
            for y in range(start_y, int(oy) + height + TILE, TILE):
                surface.blit(self._tile, (x - ox, y - oy))
        surface.set_clip(None)
        pulse = 0.75 + 0.25 * math.sin(self._time * 2)
        pygame.draw.rect(surface, scale_color(ARENA_EDGE, pulse), arena, 6)
        pygame.draw.rect(surface, scale_color(ARENA_EDGE, 0.5), arena.inflate(18, 18), 2)

    # ------------------------------------------------------------------
    def _draw_pickups(self, surface, world, ox, oy, view):
        t = self._time
        for pickup in world.pickups:
            pos = pickup.pos
            if not view.collidepoint(pos):
                continue
            x, y = pos.x - ox, pos.y - oy
            kind = pickup.kind
            if kind == "xp":
                r = pickup.radius
                bob = math.sin(t * 4 + pos.x * 0.05) * 2
                pts = [(x, y - r * 1.3 + bob), (x + r, y + bob), (x, y + r * 1.3 + bob), (x - r, y + bob)]
                if r >= 7:
                    blit_glow(surface, (x, y), r * 3, scale_color(pickup.color, 0.6))
                pygame.draw.polygon(surface, pickup.color, pts)
                pygame.draw.polygon(surface, WHITE, pts, 1)
            elif kind == "heal":
                blit_glow(surface, (x, y), 26, (140, 40, 60))
                pygame.draw.circle(surface, pickup.color, (int(x - 4), int(y - 2)), 6)
                pygame.draw.circle(surface, pickup.color, (int(x + 4), int(y - 2)), 6)
                pygame.draw.polygon(surface, pickup.color, [(x - 10, y), (x + 10, y), (x, y + 11)])
            elif kind == "magnet":
                blit_glow(surface, (x, y), 28, (60, 60, 120))
                pygame.draw.arc(surface, (230, 80, 90), (x - 10, y - 10, 20, 20), 0, math.pi, 5)
                pygame.draw.rect(surface, (230, 80, 90), (x - 10, y - 1, 5, 9))
                pygame.draw.rect(surface, (230, 80, 90), (x + 5, y - 1, 5, 9))
                pygame.draw.rect(surface, WHITE, (x - 10, y + 6, 5, 3))
                pygame.draw.rect(surface, WHITE, (x + 5, y + 6, 5, 3))
            elif kind == "core":
                blit_glow(surface, (x, y), 70 + 10 * math.sin(t * 5), (160, 120, 40))
                star = []
                for i in range(10):
                    radius = 20 if i % 2 == 0 else 9
                    angle = t * 2 + i * math.tau / 10
                    star.append((x + math.cos(angle) * radius, y + math.sin(angle) * radius))
                pygame.draw.polygon(surface, pickup.color, star)
                pygame.draw.polygon(surface, WHITE, star, 2)

    # ------------------------------------------------------------------
    def _enemy_color(self, enemy):
        color = enemy.color
        if enemy.has_status("frozen"):
            return lerp_color(color, (190, 240, 255), 0.75)
        if enemy.has_status("wet"):
            color = lerp_color(color, (70, 130, 255), 0.35)
        if enemy.has_status("burning") and int(self._time * 12) % 2 == 0:
            color = lerp_color(color, (255, 140, 40), 0.35)
        return color

    def _draw_enemies(self, surface, world, ox, oy, view):
        t = self._time
        player_pos = world.player.pos
        for enemy in world.enemies:
            pos = enemy.pos
            if not view.collidepoint(pos) and not enemy.is_boss:
                continue
            x, y = pos.x - ox, pos.y - oy
            r = enemy.radius
            pygame.draw.ellipse(surface, (6, 6, 14), (x - r, y + r * 0.5, r * 2, r * 0.8))
            color = (255, 255, 255) if enemy.flash > 0 else self._enemy_color(enemy)
            outline = scale_color(color, 0.55)
            shape = enemy.shape
            facing = enemy.facing
            if shape == "circle":
                pygame.draw.circle(surface, color, (int(x), int(y)), r)
                pygame.draw.circle(surface, outline, (int(x), int(y)), r, 2)
                self._eyes(surface, x, y, facing, r)
            elif shape == "triangle":
                tip = (x + facing.x * r * 1.4, y + facing.y * r * 1.4)
                side = Vector2(-facing.y, facing.x) * r
                back = (x - facing.x * r, y - facing.y * r)
                pts = [tip, (back[0] + side.x, back[1] + side.y), (back[0] - side.x, back[1] - side.y)]
                pygame.draw.polygon(surface, color, pts)
                pygame.draw.polygon(surface, outline, pts, 2)
            elif shape == "square":
                pts = regular_polygon((x, y), r * 1.25, 4, enemy.age * 0.6 + math.pi / 4)
                pygame.draw.polygon(surface, color, pts)
                pygame.draw.polygon(surface, outline, pts, 3)
                inner = regular_polygon((x, y), r * 0.6, 4, enemy.age * 0.6 + math.pi / 4)
                pygame.draw.polygon(surface, scale_color(color, 0.7), inner)
                self._eyes(surface, x, y, facing, r * 0.8)
            elif shape == "diamond":
                pts = regular_polygon((x, y), r * 1.3, 4, 0)
                pygame.draw.polygon(surface, color, pts)
                pygame.draw.polygon(surface, outline, pts, 2)
                blit_glow(surface, (x, y), 14, scale_color(enemy.color, 0.8))
                pygame.draw.circle(surface, WHITE, (int(x), int(y)), 3)
            elif shape == "elite":
                pulse = 0.6 + 0.4 * math.sin(t * 6)
                blit_glow(surface, (x, y), r * 3.2, scale_color(enemy.color, 0.5 * pulse))
                spikes = []
                for i in range(12):
                    radius = r * (1.35 if i % 2 == 0 else 0.95)
                    angle = enemy.age * 1.5 + i * math.tau / 12
                    spikes.append((x + math.cos(angle) * radius, y + math.sin(angle) * radius))
                pygame.draw.polygon(surface, color, spikes)
                pygame.draw.polygon(surface, (255, 220, 120), spikes, 2)
                self._eyes(surface, x, y, facing, r * 0.8, (255, 230, 120))
            elif shape == "boss":
                self._draw_boss(surface, enemy, x, y, color, player_pos)
            if enemy.has_status("frozen"):
                pygame.draw.polygon(surface, (235, 250, 255), regular_polygon((x, y), r * 1.25, 6, 0.3), 2)
            if enemy.has_status("electrified") and int(t * 20) % 2 == 0:
                pygame.draw.circle(surface, STATUS_COLORS["electrified"], (int(x), int(y)), r + 3, 1)
            if enemy.has_status("slowed") and not enemy.has_status("frozen"):
                pygame.draw.ellipse(surface, STATUS_COLORS["slowed"], (x - r, y + r * 0.55, r * 2, r * 0.7), 1)
            if enemy.is_telegraphing():
                warn = 0.5 + 0.5 * math.sin(t * 30)
                pygame.draw.circle(surface, lerp_color((255, 60, 60), WHITE, warn), (int(x), int(y)),
                                   int(r * 1.6), 3)
            self._status_pips(surface, enemy, x, y - r - 8)
            if (enemy.is_elite or enemy.kind == "tank") and enemy.hp_ratio < 1:
                w = r * 2
                pygame.draw.rect(surface, (40, 10, 20), (x - w / 2, y - r - 6, w, 4))
                pygame.draw.rect(surface, (255, 70, 90), (x - w / 2, y - r - 6, w * enemy.hp_ratio, 4))

    def _eyes(self, surface, x, y, facing, r, color=(255, 255, 255)):
        side = Vector2(-facing.y, facing.x) * r * 0.35
        front = facing * r * 0.35
        for sign in (1, -1):
            ex, ey = x + front.x + side.x * sign, y + front.y + side.y * sign
            pygame.draw.circle(surface, color, (int(ex), int(ey)), max(2, int(r * 0.22)))
            pygame.draw.circle(surface, DARK, (int(ex + facing.x * 1.5), int(ey + facing.y * 1.5)),
                               max(1, int(r * 0.11)))

    def _status_pips(self, surface, enemy, x, y):
        names = [n for n in enemy.status_names() if n != "slowed"][:4]
        if not names:
            return
        start = x - (len(names) - 1) * 5
        for i, name in enumerate(names):
            pygame.draw.circle(surface, STATUS_COLORS[name], (int(start + i * 10), int(y)), 3)

    def _draw_boss(self, surface, boss, x, y, color, player_pos):
        t = self._time
        r = boss.radius
        rage = boss.enraged
        glow_color = (200, 40, 60) if rage else scale_color(boss.color, 0.7)
        blit_glow(surface, (x, y), r * 3 + 10 * math.sin(t * 4), glow_color)
        spikes = []
        for i in range(16):
            radius = r * (1.3 if i % 2 == 0 else 1.0)
            angle = -boss.age * (1.6 if rage else 0.8) + i * math.tau / 16
            spikes.append((x + math.cos(angle) * radius, y + math.sin(angle) * radius))
        pygame.draw.polygon(surface, scale_color(color, 0.6), spikes)
        pygame.draw.circle(surface, color, (int(x), int(y)), int(r * 0.95))
        pygame.draw.circle(surface, scale_color(color, 0.5), (int(x), int(y)), int(r * 0.95), 4)
        # one big eye that follows the player
        look = player_pos - boss.pos
        look = look.normalize() * r * 0.25 if look.length_squared() > 0 else Vector2()
        pygame.draw.circle(surface, (250, 240, 250), (int(x), int(y)), int(r * 0.45))
        iris = (255, 60, 80) if rage else (120, 40, 200)
        pygame.draw.circle(surface, iris, (int(x + look.x), int(y + look.y)), int(r * 0.25))
        pygame.draw.circle(surface, DARK, (int(x + look.x * 1.2), int(y + look.y * 1.2)), int(r * 0.11))

    # ------------------------------------------------------------------
    def _draw_player(self, surface, player, ox, oy):
        t = self._time
        pos = player.pos
        x, y = pos.x - ox, pos.y - oy
        r = player.radius
        elements = player.elements
        main_color = elements[0].color if elements else ACCENT
        blit_alpha_circle(surface, (x, y), player.stats.pickup_radius, (120, 160, 255), 14, 1)
        pygame.draw.ellipse(surface, (6, 6, 14), (x - r, y + r * 0.6, r * 2, r * 0.8))
        blit_glow(surface, (x, y), r * 3.5, scale_color(main_color, 0.55))
        visible = not player.invulnerable or int(t * 16) % 2 == 0
        if visible:
            body = (255, 120, 130) if player.hurt_flash > 0 else (64, 54, 120)
            pygame.draw.circle(surface, body, (int(x), int(y)), r)
            pygame.draw.circle(surface, (190, 170, 255), (int(x), int(y)), r, 2)
            facing = player.facing
            tip = (x + facing.x * (r + 8), y + facing.y * (r + 8))
            side = Vector2(-facing.y, facing.x) * 6
            base = (x + facing.x * (r - 1), y + facing.y * (r - 1))
            pygame.draw.polygon(surface, (220, 210, 255),
                                [tip, (base[0] + side.x, base[1] + side.y), (base[0] - side.x, base[1] - side.y)])
            gem = regular_polygon((x, y), 7, 4, t * 2)
            pygame.draw.polygon(surface, main_color, gem)
            pygame.draw.polygon(surface, WHITE, gem, 1)
        # orbiting orbs: one per owned element
        count = len(elements)
        for i, element in enumerate(elements):
            angle = t * 2.2 + i * math.tau / max(1, count)
            ex, ey = x + math.cos(angle) * (r + 14), y + math.sin(angle) * (r + 14)
            blit_glow(surface, (ex, ey), 14, scale_color(element.color, 0.8))
            pygame.draw.circle(surface, element.color, (int(ex), int(ey)), 5)

    # ------------------------------------------------------------------
    def _draw_projectiles(self, surface, world, ox, oy, view):
        for proj in world.projectiles:
            pos = proj.pos
            if not view.collidepoint(pos):
                continue
            x, y = pos.x - ox, pos.y - oy
            r = proj.radius
            vel = proj.vel
            direction = vel.normalize() if vel.length_squared() > 0 else Vector2(1, 0)
            kind = proj.kind
            color = proj.color
            if kind == "fireball":
                for k in range(1, 4):
                    tx, ty = x - direction.x * r * 1.2 * k, y - direction.y * r * 1.2 * k
                    pygame.draw.circle(surface, scale_color(color, 1 - k * 0.25), (int(tx), int(ty)),
                                       max(1, int(r * (1 - k * 0.22))))
                blit_glow(surface, (x, y), r * 3.2, (200, 80, 20))
                pygame.draw.circle(surface, color, (int(x), int(y)), int(r))
                pygame.draw.circle(surface, (255, 230, 140), (int(x), int(y)), max(1, int(r * 0.55)))
            elif kind == "water":
                tail = (x - direction.x * r * 2.2, y - direction.y * r * 2.2)
                pygame.draw.line(surface, scale_color(color, 0.7), tail, (x, y), int(r * 1.3))
                pygame.draw.circle(surface, color, (int(x), int(y)), int(r))
                pygame.draw.circle(surface, (200, 230, 255), (int(x + 2), int(y - 2)), max(1, int(r * 0.35)))
            elif kind == "ice":
                side = Vector2(-direction.y, direction.x) * r * 0.8
                tip = (x + direction.x * r * 2.2, y + direction.y * r * 2.2)
                back = (x - direction.x * r, y - direction.y * r)
                pts = [tip, (back[0] + side.x, back[1] + side.y), (back[0] - side.x, back[1] - side.y)]
                blit_glow(surface, (x, y), r * 3, (60, 110, 140))
                pygame.draw.polygon(surface, color, pts)
                pygame.draw.polygon(surface, WHITE, pts, 1)
            elif kind == "rock":
                pts = regular_polygon((x, y), r, 6, proj.age * 7)
                pygame.draw.ellipse(surface, (6, 6, 14), (x - r, y + r * 0.6, r * 2, r * 0.7))
                pygame.draw.polygon(surface, color, pts)
                pygame.draw.polygon(surface, scale_color(color, 0.5), pts, 3)
                pygame.draw.circle(surface, scale_color(color, 1.3), (int(x - r * 0.3), int(y - r * 0.3)),
                                   max(1, int(r * 0.25)))
            elif kind == "wind":
                base_angle = math.atan2(direction.y, direction.x)
                pts = []
                for i in range(9):
                    a = base_angle - 1.1 + 2.2 * i / 8
                    pts.append((x - direction.x * r * 0.6 + math.cos(a) * r * 1.4,
                                y - direction.y * r * 0.6 + math.sin(a) * r * 1.4))
                blit_glow(surface, (x, y), r * 2.4, (40, 110, 70))
                pygame.draw.lines(surface, color, False, pts, 4)
                pygame.draw.lines(surface, WHITE, False, pts[2:-2], 1)
            else:
                pygame.draw.circle(surface, color, (int(x), int(y)), int(r))
        for bullet in world.enemy_bullets:
            pos = bullet.pos
            if not view.collidepoint(pos):
                continue
            x, y = pos.x - ox, pos.y - oy
            r = bullet.radius
            blit_glow(surface, (x, y), r * 3, scale_color(bullet.color, 0.6))
            pygame.draw.circle(surface, bullet.color, (int(x), int(y)), int(r))
            pygame.draw.circle(surface, WHITE, (int(x), int(y)), max(1, int(r * 0.45)))

    # ------------------------------------------------------------------
    def _draw_zones(self, surface, world, ox, oy, layer):
        t = self._time
        for zone in world.effects:
            if zone.layer != layer:
                continue
            pos = zone.pos
            x, y = pos.x - ox, pos.y - oy
            r = zone.radius
            if x < -r - 300 or y < -r - 300 or x > SCREEN_W + r + 300 or y > SCREEN_H + r + 300:
                continue
            fade = min(1.0, (1 - zone.progress) * 4, zone.age * 6)
            kind = zone.kind
            if kind == "steam":
                for i in range(5):
                    a = zone.age * 0.8 + i * math.tau / 5
                    px, py = x + math.cos(a) * r * 0.45, y + math.sin(a) * r * 0.45
                    blit_alpha_circle(surface, (px, py), r * 0.6, (230, 235, 245), 55 * fade)
            elif kind == "tornado":
                blit_alpha_circle(surface, (x, y), r, (255, 120, 40), 40 * fade)
                blit_glow(surface, (x, y), r * 1.2, scale_color((220, 90, 20), fade))
                for arm in range(3):
                    pts = []
                    for i in range(12):
                        f = i / 11
                        angle = zone.age * 9 + arm * math.tau / 3 + f * 3.4
                        pts.append((x + math.cos(angle) * r * f, y + math.sin(angle) * r * f - f * 10))
                    pygame.draw.lines(surface, lerp_color((255, 220, 120), (255, 90, 30), arm / 2), False, pts, 4)
            elif kind == "meteor":
                if not zone.impacted:
                    fp = zone.fall_progress
                    blit_alpha_circle(surface, (x, y), r * (0.3 + 0.7 * fp), (0, 0, 0), 90)
                    pygame.draw.circle(surface, (255, 80, 60), (int(x), int(y)), int(r), 2)
                    mx, my = x - 220 * (1 - fp), y - 420 * (1 - fp)
                    if fp > 0:
                        pygame.draw.line(surface, (255, 150, 60), (mx - 90 * (1 - fp) - 40, my - 160 * (1 - fp) - 70),
                                         (mx, my), 8)
                        blit_glow(surface, (mx, my), 60, (220, 90, 20))
                        pygame.draw.circle(surface, (120, 70, 40), (int(mx), int(my)), 18)
                        pygame.draw.circle(surface, (255, 180, 80), (int(mx), int(my)), 18, 3)
                else:
                    blit_alpha_circle(surface, (x, y), r * 0.6, (255, 100, 30), 70 * fade)
                    blit_glow(surface, (x, y), r * 0.8, scale_color((180, 60, 10), fade))
            elif kind == "electric_storm":
                blit_alpha_circle(surface, (x, y), r, (40, 70, 140), 45 * fade)
                pygame.draw.circle(surface, scale_color((120, 200, 255), fade), (int(x), int(y)), int(r), 2)
                rng = random.Random(int(zone.age * 10))
                for i in range(22):
                    angle = rng.random() * math.tau
                    dist = math.sqrt(rng.random()) * r
                    px, py = x + math.cos(angle) * dist, y + math.sin(angle) * dist
                    pygame.draw.line(surface, (150, 190, 255), (px, py), (px - 3, py + 12), 1)
            elif kind == "blizzard":
                blit_alpha_circle(surface, (x, y), r, (200, 230, 255), 40 * fade)
                pygame.draw.circle(surface, scale_color((220, 245, 255), fade), (int(x), int(y)), int(r), 2)
                for i in range(30):
                    orbit = r * (0.25 + 0.75 * ((i * 37) % 100) / 100)
                    angle = zone.age * (2.5 + (i % 5) * 0.4) + i * 1.7
                    px, py = x + math.cos(angle) * orbit, y + math.sin(angle) * orbit
                    pygame.draw.circle(surface, WHITE, (int(px), int(py)), 2 + i % 2)
            elif kind == "magnet_field":
                blit_alpha_circle(surface, (x, y), r, (120, 90, 40), 40 * fade)
                for k in range(3):
                    f = 1 - ((zone.age * 1.6 + k / 3) % 1.0)
                    pygame.draw.circle(surface, lerp_color((255, 230, 90), (190, 130, 70), f),
                                       (int(x), int(y)), max(3, int(r * f)), 2)
                blit_glow(surface, (x, y), 30 + 50 * zone.progress, (180, 160, 40))
            elif kind == "sandstorm":
                blit_alpha_circle(surface, (x, y), r, (210, 170, 100), 55 * fade)
                for i in range(36):
                    orbit = r * (0.2 + 0.8 * ((i * 53) % 100) / 100)
                    angle = zone.age * (3.0 + (i % 4) * 0.5) + i * 2.1
                    px, py = x + math.cos(angle) * orbit, y + math.sin(angle) * orbit
                    pygame.draw.circle(surface, (235, 200, 140), (int(px), int(py)), 2)
                pygame.draw.circle(surface, scale_color((240, 210, 150), fade), (int(x), int(y)), int(r), 1)
            elif kind == "crystal_spike":
                if not zone.erupted:
                    pygame.draw.circle(surface, (120, 170, 210), (int(x), int(y)), int(r * 0.5), 1)
                else:
                    rise = zone.rise
                    if rise > 0:
                        blit_glow(surface, (x, y), r * 1.4, scale_color((70, 120, 160), rise))
                        for k, (dx, h) in enumerate(((-r * 0.45, 0.8), (0, 1.3), (r * 0.45, 0.9))):
                            height = r * 1.4 * h * rise
                            base_y = y + r * 0.3
                            pts = [(x + dx - r * 0.22, base_y), (x + dx, base_y - height),
                                   (x + dx + r * 0.22, base_y)]
                            pygame.draw.polygon(surface, (180, 230, 255) if k != 1 else (225, 250, 255), pts)
                            pygame.draw.polygon(surface, WHITE, pts, 1)
            elif kind == "thunderstorm":
                pygame.draw.circle(surface, scale_color((150, 200, 255), fade * 0.6), (int(x), int(y)), int(r), 1)
                for i in range(6):
                    angle = i * math.tau / 6 + t * 0.4
                    px, py = x + math.cos(angle) * r * 0.35, y + math.sin(angle) * r * 0.25
                    blit_alpha_circle(surface, (px, py), r * 0.38, (50, 55, 80), 120 * fade)
                blit_alpha_circle(surface, (x, y), r * 0.42, (70, 75, 105), 140 * fade)
