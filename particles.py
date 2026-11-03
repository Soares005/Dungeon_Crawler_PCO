"""Visual feedback: particles, damage numbers, lightning arcs, rings, banners.

This is pure presentation. EffectsDirector reads the GameEvents produced by
the logic layer and turns them into effects and sounds.
"""
import math
import random

import pygame

from gfx import blit_glow, jagged_line, scale_color
from settings import ELEMENT_COLORS, ICE, EARTH, WHITE, SCREEN_W

MAX_PARTICLES = 1400
MAX_NUMBERS = 70


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "color", "drag", "gravity", "glow")

    def __init__(self, x, y, vx, vy, life, size, color, drag=3.0, gravity=0.0, glow=False):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.size = size
        self.color = color
        self.drag = drag
        self.gravity = gravity
        self.glow = glow


class ParticleSystem:
    """A reusable pool of simple particles."""

    def __init__(self):
        self._particles = []
        self._rng = random.Random()

    def __len__(self):
        return len(self._particles)

    def emit(self, pos, color, count=8, speed=120, life=0.5, size=3.0, spread=math.tau,
             direction=0.0, drag=3.0, gravity=0.0, glow=False):
        rng = self._rng
        room = MAX_PARTICLES - len(self._particles)
        for _ in range(min(count, room)):
            angle = direction + rng.uniform(-spread / 2, spread / 2)
            s = speed * rng.uniform(0.35, 1.0)
            self._particles.append(Particle(pos[0], pos[1], math.cos(angle) * s, math.sin(angle) * s,
                                            life * rng.uniform(0.6, 1.0), size * rng.uniform(0.6, 1.2),
                                            color, drag, gravity, glow))

    def update(self, dt):
        alive = []
        for p in self._particles:
            p.life -= dt
            if p.life <= 0:
                continue
            factor = max(0.0, 1.0 - p.drag * dt)
            p.vx *= factor
            p.vy = p.vy * factor + p.gravity * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            alive.append(p)
        self._particles = alive

    def draw(self, surface, camera):
        ox, oy = camera.offset
        width, height = surface.get_size()
        draw_circle = pygame.draw.circle
        for p in self._particles:
            x, y = p.x - ox, p.y - oy
            if x < -20 or y < -20 or x > width + 20 or y > height + 20:
                continue
            t = p.life / p.max_life
            radius = p.size * (0.4 + 0.6 * t)
            if p.glow:
                blit_glow(surface, (x, y), radius * 3, scale_color(p.color, t))
            if radius >= 1:
                draw_circle(surface, p.color, (int(x), int(y)), int(radius))


class FloatingText:
    __slots__ = ("x", "y", "vy", "life", "max_life", "surface")

    def __init__(self, x, y, surface, life=0.75, rise=55):
        self.x, self.y = x, y
        self.vy = -rise
        self.life = self.max_life = life
        self.surface = surface


class LightningArc:
    __slots__ = ("points", "color", "life", "max_life", "width")

    def __init__(self, points, color, life, width):
        self.points = points
        self.color = color
        self.life = self.max_life = life
        self.width = width


class Ring:
    __slots__ = ("x", "y", "radius", "color", "life", "max_life", "width")

    def __init__(self, x, y, radius, color, life=0.35, width=4):
        self.x, self.y = x, y
        self.radius = radius
        self.color = color
        self.life = self.max_life = life
        self.width = width


class EffectsDirector:
    """Consumes logic events and manages every short-lived visual effect."""

    def __init__(self, fonts, audio, settings):
        self._fonts = fonts
        self._audio = audio
        self._settings = settings
        self._rng = random.Random()
        self.particles = ParticleSystem()
        self._texts = []
        self._arcs = []
        self._rings = []
        self._toasts = []          # (text, color, remaining)
        self._banner = None        # [title, subtitle, color, remaining, total]
        self._flash = 0.0
        self._flash_color = WHITE
        self._hurt = 0.0
        self._number_cache = {}

    @property
    def hurt_overlay(self):
        return self._hurt

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def handle_events(self, events, camera):
        play = self._audio.play
        for event in events:
            kind = event.kind
            x, y = event.pos
            if kind == "hit":
                if event.text != "dot":
                    self.particles.emit(event.pos, event.color, count=3, speed=140, life=0.25, size=2.5)
                    play("hit", 0.5, 0.045)
                self._damage_number(x, y, event.value, event.color, event.big, event.text == "dot")
            elif kind == "impact":
                self.particles.emit(event.pos, event.color, count=2, speed=90, life=0.2, size=2)
            elif kind == "death":
                count = 26 if event.big else 9
                self.particles.emit(event.pos, event.color, count=count, speed=200 if event.big else 150,
                                    life=0.55, size=4 if event.big else 3, glow=event.big)
                if event.big:
                    self._rings.append(Ring(x, y, event.value * 3, event.color, 0.5, 6))
                    camera.shake(5)
                play("death", 0.5, 0.06)
            elif kind == "explosion":
                radius = event.value
                self._rings.append(Ring(x, y, radius, event.color, 0.35, 5))
                self.particles.emit(event.pos, event.color, count=int(8 + radius / 8), speed=radius * 3,
                                    life=0.45, size=4, glow=radius > 70)
                play("explosion", 0.45 if radius > 70 else 0.25, 0.08)
            elif kind == "reaction":
                self._float_text(x, y - 22, event.text.upper() + "!", event.color, 18, life=0.9, rise=40)
                self._rings.append(Ring(x, y, 46, event.color, 0.3, 3))
                play("reaction", 0.6, 0.12)
            elif kind == "lightning":
                width = 3 if event.big else 2
                pts = jagged_line(event.points, self._rng, jitter=12 if event.big else 8)
                self._arcs.append(LightningArc(pts, event.color, 0.22 if event.big else 0.16, width))
                for px, py in event.points[1:]:
                    self.particles.emit((px, py), event.color, count=3, speed=120, life=0.25, size=2)
                play("thunder" if event.big else "zap", 0.5, 0.09)
            elif kind == "freeze":
                self.particles.emit(event.pos, ELEMENT_COLORS[ICE], count=7, speed=110, life=0.45, size=3)
                play("freeze", 0.4, 0.12)
            elif kind == "wildfire":
                self._rings.append(Ring(x, y, event.value, event.color, 0.4, 3))
                self.particles.emit(event.pos, event.color, count=16, speed=260, life=0.5, size=3, glow=True)
            elif kind == "dust":
                self.particles.emit(event.pos, ELEMENT_COLORS[EARTH], count=5, speed=100, life=0.4, size=3)
            elif kind == "spike":
                self.particles.emit(event.pos, (210, 245, 255), count=4, speed=90, life=0.35, size=2.5,
                                    direction=-math.pi / 2, spread=1.2)
            elif kind == "shake":
                camera.shake(event.value)
            elif kind == "level_up":
                self._rings.append(Ring(x, y, 120, event.color, 0.6, 6))
                self.particles.emit(event.pos, event.color, count=30, speed=260, life=0.7, size=3, glow=True)
                play("level_up", 0.8, 0.3)
            elif kind == "pickup":
                play("pickup", 0.35, 0.03)
            elif kind == "heal":
                self.particles.emit(event.pos, (120, 255, 150), count=14, speed=120, life=0.6, size=3,
                                    gravity=-80)
                self._float_text(x, y - 24, f"+{int(event.value)}", (120, 255, 150), 18)
                play("heal", 0.6)
            elif kind == "core":
                self._rings.append(Ring(x, y, 220, event.color, 0.8, 8))
                self.particles.emit(event.pos, event.color, count=60, speed=360, life=0.9, size=4, glow=True)
                self.show_banner(event.text, "Choose a powerful reward", event.color)
                camera.shake(8)
                play("unlock", 0.9, 0.5)
            elif kind == "text":
                self._float_text(x, y - 40, event.text, event.color, 24, life=1.4, rise=30)
            elif kind == "player_hurt":
                self._hurt = 0.35
                camera.shake(4)
                self.particles.emit(event.pos, (255, 80, 90), count=8, speed=160, life=0.35, size=3)
                play("hurt", 0.7, 0.15)
            elif kind == "player_death":
                self.particles.emit(event.pos, (255, 255, 255), count=80, speed=380, life=1.2, size=4, glow=True)
                self._rings.append(Ring(x, y, 260, (255, 255, 255), 1.0, 8))
                camera.shake(12)
                play("explosion", 1.0, 0.0)
            elif kind == "boss_warning":
                self.show_banner("WARNING", event.text, (255, 70, 90), 3.0)
                play("boss", 0.9, 1.0)
            elif kind == "boss_spawn":
                self.show_banner(event.text.upper(), "has entered the arena", event.color, 2.6)
                camera.shake(10)
                play("boss", 1.0, 1.0)
            elif kind == "boss_defeated":
                self.show_banner("BOSS DEFEATED", event.text, (255, 210, 90), 2.6)
                self._flash, self._flash_color = 0.35, (255, 240, 200)
                camera.shake(14)
            elif kind == "fusion_cast":
                play("fusion", 0.35, 0.2)
            elif kind == "fusion_unlocked":
                self.show_banner("FUSION UNLOCKED", event.text, event.color, 2.4)
                self._flash, self._flash_color = 0.3, event.color
                self._rings.append(Ring(x, y, 260, event.color, 0.7, 8))
                self.particles.emit(event.pos, event.color, count=50, speed=340, life=0.8, size=4, glow=True)
                play("unlock", 1.0, 0.5)
            elif kind == "discovery":
                self._toasts.append([event.text, event.color, 3.5])
                play("unlock", 0.6, 0.6)
            elif kind == "sound":
                play(event.text, 0.35, 0.08)

    def _number_surface(self, text, color, size):
        key = (text, color, size)
        surface = self._number_cache.get(key)
        if surface is None:
            font = self._fonts.get(size, bold=True)
            main = font.render(text, True, color)
            surface = pygame.Surface((main.get_width() + 2, main.get_height() + 2), pygame.SRCALPHA)
            surface.blit(font.render(text, True, (10, 10, 20)), (2, 2))
            surface.blit(main, (0, 0))
            self._number_cache[key] = surface
            if len(self._number_cache) > 900:
                self._number_cache.clear()
        return surface

    def _damage_number(self, x, y, value, color, big, dot):
        if not self._settings.damage_numbers or value < 0.5:
            return
        if len(self._texts) >= MAX_NUMBERS and not big:
            return
        if dot:
            color, size = scale_color(color, 0.8), 13
        else:
            size = 22 if big else 16
            color = (255, 255, 255) if big else color
        text = str(int(round(value)))
        surface = self._number_surface(text, color, size)
        self._texts.append(FloatingText(x + self._rng.uniform(-8, 8), y - 14, surface,
                                        life=0.8 if big else 0.6, rise=70 if big else 50))

    def _float_text(self, x, y, text, color, size, life=0.9, rise=50):
        surface = self._number_surface(text, color, size)
        self._texts.append(FloatingText(x, y, surface, life, rise))

    def show_banner(self, title, subtitle, color, duration=2.2):
        self._banner = [title, subtitle, color, duration, duration]

    def emit_status_particles(self, world, camera_rect):
        """Ambient particles for enemies with visible statuses (fire, sparks)."""
        rng = self._rng
        for enemy in world.enemies:
            if not camera_rect.collidepoint(enemy.pos):
                continue
            if enemy.has_status("burning") and rng.random() < 0.18:
                self.particles.emit(enemy.pos, (255, 140, 40), count=1, speed=40, life=0.45, size=3,
                                    direction=-math.pi / 2, spread=1.0, gravity=-60)
            if enemy.has_status("electrified") and rng.random() < 0.08:
                self.particles.emit(enemy.pos, (255, 240, 120), count=2, speed=150, life=0.15, size=2)

    # ------------------------------------------------------------------
    def update(self, dt):
        self.particles.update(dt)
        for text in self._texts:
            text.life -= dt
            text.y += text.vy * dt
            text.vy *= max(0.0, 1 - 2.5 * dt)
        self._texts = [t for t in self._texts if t.life > 0]
        for arc in self._arcs:
            arc.life -= dt
        self._arcs = [a for a in self._arcs if a.life > 0]
        for ring in self._rings:
            ring.life -= dt
        self._rings = [r for r in self._rings if r.life > 0]
        for toast in self._toasts:
            toast[2] -= dt
        self._toasts = [t for t in self._toasts if t[2] > 0][-4:]
        if self._banner is not None:
            self._banner[3] -= dt
            if self._banner[3] <= 0:
                self._banner = None
        self._flash = max(0.0, self._flash - dt)
        self._hurt = max(0.0, self._hurt - dt)

    def draw_world_effects(self, surface, camera):
        """Effects that live in world space (drawn under the HUD)."""
        ox, oy = camera.offset
        for ring in self._rings:
            t = 1 - ring.life / ring.max_life
            radius = int(ring.radius * (0.3 + 0.7 * t))
            width = max(1, int(ring.width * (1 - t)))
            if radius > width:
                pygame.draw.circle(surface, scale_color(ring.color, 1 - t * 0.6),
                                   (int(ring.x - ox), int(ring.y - oy)), radius, width)
        for arc in self._arcs:
            pts = [(px - ox, py - oy) for px, py in arc.points]
            t = arc.life / arc.max_life
            if len(pts) >= 2:
                pygame.draw.lines(surface, scale_color(arc.color, 0.6 + 0.4 * t), False, pts, arc.width + 2)
                pygame.draw.lines(surface, (255, 255, 255), False, pts, max(1, arc.width - 1))
                blit_glow(surface, pts[-1], 18, scale_color(arc.color, t))
        self.particles.draw(surface, camera)
        for text in self._texts:
            t = text.life / text.max_life
            surf = text.surface
            if t < 0.3:
                surf = surf.copy()
                surf.set_alpha(int(255 * t / 0.3))
            surface.blit(surf, (int(text.x - ox - surf.get_width() / 2), int(text.y - oy)))

    def draw_screen_effects(self, surface):
        """Full-screen overlays: hurt vignette, flashes, banners, toasts."""
        width, height = surface.get_size()
        if self._hurt > 0:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            alpha = int(120 * self._hurt / 0.35)
            pygame.draw.rect(overlay, (255, 30, 50, alpha), overlay.get_rect(), 26, border_radius=8)
            surface.blit(overlay, (0, 0))
        if self._flash > 0:
            overlay = pygame.Surface((width, height))
            overlay.fill(self._flash_color)
            overlay.set_alpha(int(110 * self._flash / 0.35))
            surface.blit(overlay, (0, 0))
        if self._banner is not None:
            title, subtitle, color, remaining, total = self._banner
            t = remaining / total
            alpha = int(255 * min(1.0, t * 4, (1 - t) * 8 + 0.2))
            big = self._fonts.get(54, bold=True).render(title, True, color)
            small = self._fonts.get(24).render(subtitle, True, WHITE)
            band = pygame.Surface((width, 120), pygame.SRCALPHA)
            band.fill((8, 8, 18, min(170, alpha)))
            band.blit(big, (width / 2 - big.get_width() / 2, 14))
            band.blit(small, (width / 2 - small.get_width() / 2, 80))
            band.set_alpha(alpha)
            surface.blit(band, (0, 150))
        for i, (text, color, remaining) in enumerate(self._toasts):
            label = self._fonts.get(20, bold=True).render(text, True, color)
            box = pygame.Rect(0, 0, label.get_width() + 36, 40)
            box.topright = (SCREEN_W - 16, 70 + i * 48)
            panel = pygame.Surface(box.size, pygame.SRCALPHA)
            panel.fill((14, 14, 30, 220))
            pygame.draw.rect(panel, color, panel.get_rect(), 2, border_radius=8)
            panel.blit(label, (18, 20 - label.get_height() / 2))
            panel.set_alpha(int(255 * min(1.0, remaining / 0.5)))
            surface.blit(panel, box.topleft)
