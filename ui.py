"""User-interface building blocks: fonts, text, buttons, menus, icons, HUD, cards."""
import math

import pygame

from gfx import blit_glow, scale_color, regular_polygon
from settings import (WHITE, GREY, PANEL, PANEL_LIGHT, ACCENT, HP_RED, XP_BLUE, GOLD,
                      ELEMENT_COLORS, SCREEN_W, SCREEN_H, FIRE, WATER, LIGHTNING, ICE, EARTH, WIND)
from fusions import FUSIONS_BY_ID


class Fonts:
    """Caches fonts by size. Falls back to pygame's default font if needed."""

    def __init__(self):
        self._cache = {}

    def get(self, size, bold=False):
        key = (size, bold)
        font = self._cache.get(key)
        if font is None:
            try:
                font = pygame.font.SysFont("segoeui,trebuchetms,arial,dejavusans", size, bold=bold)
            except (pygame.error, OSError):
                font = pygame.font.Font(None, int(size * 1.3))
            self._cache[key] = font
        return font


def draw_text(surface, text, font, color, pos, anchor="topleft", shadow=True):
    image = font.render(str(text), True, color)
    rect = image.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    if shadow:
        surface.blit(font.render(str(text), True, (8, 8, 16)), rect.move(2, 2))
    surface.blit(image, rect)
    return rect


def wrap_text(text, font, width):
    """Split text into lines that fit `width` pixels."""
    lines = []
    for paragraph in str(text).split("\n"):
        words = paragraph.split()
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            if font.size(test)[0] <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    return lines


def draw_wrapped(surface, text, font, color, rect, line_gap=2, anchor_center=False):
    y = rect.top
    for line in wrap_text(text, font, rect.width):
        if anchor_center:
            draw_text(surface, line, font, color, (rect.centerx, y), "midtop", shadow=False)
        else:
            draw_text(surface, line, font, color, (rect.left, y), shadow=False)
        y += font.get_linesize() + line_gap
    return y


def draw_panel(surface, rect, color=PANEL, border=PANEL_LIGHT, alpha=235, radius=14, width=2):
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, (*color, alpha), panel.get_rect(), border_radius=radius)
    if width:
        pygame.draw.rect(panel, (*border, 255), panel.get_rect(), width, border_radius=radius)
    surface.blit(panel, rect.topleft)


def dim_screen(surface, alpha=150):
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((6, 6, 14, alpha))
    surface.blit(overlay, (0, 0))


def draw_bar(surface, rect, ratio, color, back=(30, 30, 50), border=True, radius=6):
    ratio = max(0.0, min(1.0, ratio))
    pygame.draw.rect(surface, back, rect, border_radius=radius)
    if ratio > 0:
        fill = rect.copy()
        fill.width = max(radius * 2, int(rect.width * ratio))
        pygame.draw.rect(surface, color, fill, border_radius=radius)
        shine = fill.copy()
        shine.height = max(1, fill.height // 3)
        pygame.draw.rect(surface, scale_color(color, 1.3), shine, border_radius=radius)
    if border:
        pygame.draw.rect(surface, (12, 12, 22), rect, 2, border_radius=radius)


# --------------------------------------------------------------------------
# Icons (all procedural)
# --------------------------------------------------------------------------
def draw_element_icon(surface, element_id, center, size, glow=True):
    x, y = center
    color = ELEMENT_COLORS.get(element_id, WHITE)
    s = size
    if glow:
        blit_glow(surface, center, s * 1.4, scale_color(color, 0.45))
    if element_id == FIRE:
        pts = [(x, y - s * 0.9), (x + s * 0.45, y - s * 0.1), (x + s * 0.55, y + s * 0.35),
               (x, y + s * 0.75), (x - s * 0.55, y + s * 0.35), (x - s * 0.45, y - s * 0.1)]
        pygame.draw.polygon(surface, color, pts)
        inner = [(x, y - s * 0.2), (x + s * 0.25, y + s * 0.3), (x, y + s * 0.6), (x - s * 0.25, y + s * 0.3)]
        pygame.draw.polygon(surface, (255, 230, 130), inner)
    elif element_id == WATER:
        pygame.draw.circle(surface, color, (int(x), int(y + s * 0.25)), int(s * 0.5))
        pygame.draw.polygon(surface, color, [(x, y - s * 0.85), (x + s * 0.46, y + s * 0.1),
                                             (x - s * 0.46, y + s * 0.1)])
        pygame.draw.circle(surface, (200, 230, 255), (int(x - s * 0.18), int(y + s * 0.2)), max(1, int(s * 0.12)))
    elif element_id == LIGHTNING:
        pts = [(x + s * 0.15, y - s * 0.9), (x - s * 0.45, y + s * 0.1), (x - s * 0.02, y + s * 0.1),
               (x - s * 0.2, y + s * 0.9), (x + s * 0.45, y - s * 0.15), (x + s * 0.02, y - s * 0.15)]
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, WHITE, pts, 1)
    elif element_id == ICE:
        for k in range(3):
            angle = k * math.pi / 3
            dx, dy = math.cos(angle) * s * 0.85, math.sin(angle) * s * 0.85
            pygame.draw.line(surface, color, (x - dx, y - dy), (x + dx, y + dy), max(2, int(s * 0.16)))
        pygame.draw.circle(surface, WHITE, (int(x), int(y)), max(2, int(s * 0.18)))
    elif element_id == EARTH:
        pts = regular_polygon((x, y), s * 0.8, 6, 0.3)
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, scale_color(color, 0.5), pts, max(1, int(s * 0.12)))
        pygame.draw.line(surface, scale_color(color, 0.5), (x - s * 0.3, y - s * 0.2), (x + s * 0.1, y + s * 0.3), 2)
    elif element_id == WIND:
        for k, off in enumerate((-0.35, 0.05, 0.45)):
            rect = pygame.Rect(0, 0, s * (1.6 - k * 0.3), s * 0.7)
            rect.center = (x, y + off * s)
            pygame.draw.arc(surface, color, rect, 0.2, math.pi * 0.95, max(2, int(s * 0.14)))
    else:
        pygame.draw.circle(surface, color, (int(x), int(y)), int(s * 0.6))


STAT_ICON_SHAPES = {
    "damage": "sword", "move_speed": "boot", "attack_speed": "clock", "projectile_size": "expand",
    "extra_projectiles": "multi", "pickup_radius": "magnet", "max_hp": "heart", "regen": "plus",
}


def draw_stat_icon(surface, stat, center, size, color):
    x, y = center
    s = size
    blit_glow(surface, center, s * 1.3, scale_color(color, 0.35))
    shape = STAT_ICON_SHAPES.get(stat, "plus")
    if shape == "sword":
        pygame.draw.line(surface, color, (x - s * 0.6, y + s * 0.6), (x + s * 0.6, y - s * 0.6), max(3, int(s * 0.2)))
        pygame.draw.line(surface, color, (x - s * 0.55, y + s * 0.1), (x - s * 0.1, y + s * 0.55), max(3, int(s * 0.18)))
    elif shape == "boot":
        pts = [(x - s * 0.3, y - s * 0.7), (x + s * 0.1, y - s * 0.7), (x + s * 0.1, y + s * 0.2),
               (x + s * 0.7, y + s * 0.3), (x + s * 0.7, y + s * 0.6), (x - s * 0.3, y + s * 0.6)]
        pygame.draw.polygon(surface, color, pts)
    elif shape == "clock":
        pygame.draw.circle(surface, color, (int(x), int(y)), int(s * 0.7), max(2, int(s * 0.14)))
        pygame.draw.line(surface, color, (x, y), (x, y - s * 0.45), 3)
        pygame.draw.line(surface, color, (x, y), (x + s * 0.35, y), 3)
    elif shape == "expand":
        pygame.draw.circle(surface, color, (int(x), int(y)), int(s * 0.25))
        pygame.draw.circle(surface, color, (int(x), int(y)), int(s * 0.7), 2)
    elif shape == "multi":
        for k in (-1, 0, 1):
            pygame.draw.circle(surface, color, (int(x + k * s * 0.45), int(y - abs(k) * s * 0.15)), int(s * 0.22))
    elif shape == "magnet":
        rect = pygame.Rect(0, 0, s * 1.2, s * 1.2)
        rect.center = (x, y)
        pygame.draw.arc(surface, color, rect, 0, math.pi, max(3, int(s * 0.25)))
        pygame.draw.line(surface, color, (rect.left + s * 0.12, y), (rect.left + s * 0.12, y + s * 0.5), max(3, int(s * 0.25)))
        pygame.draw.line(surface, color, (rect.right - s * 0.14, y), (rect.right - s * 0.14, y + s * 0.5), max(3, int(s * 0.25)))
    elif shape == "heart":
        pygame.draw.circle(surface, color, (int(x - s * 0.3), int(y - s * 0.15)), int(s * 0.36))
        pygame.draw.circle(surface, color, (int(x + s * 0.3), int(y - s * 0.15)), int(s * 0.36))
        pygame.draw.polygon(surface, color, [(x - s * 0.64, y - s * 0.05), (x + s * 0.64, y - s * 0.05), (x, y + s * 0.7)])
    else:
        pygame.draw.rect(surface, color, (x - s * 0.15, y - s * 0.6, s * 0.3, s * 1.2))
        pygame.draw.rect(surface, color, (x - s * 0.6, y - s * 0.15, s * 1.2, s * 0.3))


_question_cache = {}


def _question_mark(size):
    image = _question_cache.get(size)
    if image is None:
        image = pygame.font.Font(None, size).render("?", True, GREY)
        _question_cache[size] = image
    return image


def draw_fusion_icon(surface, fusion_id, center, size, discovered=True):
    """A fusion is shown as its two element icons overlapping inside a ring."""
    x, y = center
    recipe = FUSIONS_BY_ID.get(fusion_id)
    if recipe is None or not discovered:
        pygame.draw.circle(surface, (60, 60, 90), (int(x), int(y)), int(size), 2)
        image = _question_mark(int(size * 1.6))
        surface.blit(image, image.get_rect(center=(int(x), int(y))))
        return
    blit_glow(surface, center, size * 1.6, scale_color(recipe.color, 0.5))
    pygame.draw.circle(surface, recipe.color, (int(x), int(y)), int(size), 2)
    a, b = sorted(recipe.elements)
    draw_element_icon(surface, a, (x - size * 0.35, y), size * 0.5, glow=False)
    draw_element_icon(surface, b, (x + size * 0.35, y), size * 0.5, glow=False)


def draw_upgrade_icon(surface, upgrade, center, size):
    kind, key = upgrade.icon
    if kind == "element":
        draw_element_icon(surface, key, center, size)
    elif kind == "fusion":
        draw_fusion_icon(surface, key, center, size)
    else:
        draw_stat_icon(surface, key, center, size, upgrade.color)


# --------------------------------------------------------------------------
# Widgets
# --------------------------------------------------------------------------
class Button:
    def __init__(self, rect, label, action, color=ACCENT):
        self._rect = pygame.Rect(rect)
        self._label = label
        self._action = action
        self._color = color

    @property
    def rect(self):
        return self._rect

    @property
    def label(self):
        return self._label

    def set_label(self, label):
        self._label = label

    def activate(self):
        self._action()

    def draw(self, surface, fonts, selected):
        rect = self._rect
        base = PANEL_LIGHT if selected else PANEL
        border = self._color if selected else (70, 74, 110)
        if selected:
            glow_rect = rect.inflate(10, 10)
            draw_panel(surface, glow_rect, scale_color(self._color, 0.35), self._color, alpha=90, radius=16, width=0)
        draw_panel(surface, rect, base, border, alpha=240, radius=12, width=2)
        draw_text(surface, self._label, fonts.get(26, bold=selected), WHITE if selected else (200, 200, 215),
                  rect.center, "center")


class Menu:
    """A vertical list of buttons controllable with keyboard and mouse."""

    def __init__(self, labels_actions, center_x, top, width=320, height=52, gap=14, audio=None):
        self._buttons = []
        for i, (label, action) in enumerate(labels_actions):
            rect = pygame.Rect(0, 0, width, height)
            rect.midtop = (center_x, top + i * (height + gap))
            self._buttons.append(Button(rect, label, action))
        self._index = 0
        self._audio = audio

    @property
    def buttons(self):
        return list(self._buttons)

    @property
    def index(self):
        return self._index

    def _play(self, name):
        if self._audio is not None:
            self._audio.play(name, 0.6, 0.02)

    def handle_event(self, event):
        """Returns True if the event was used."""
        if not self._buttons:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self._index = (self._index - 1) % len(self._buttons)
                self._play("move")
                return True
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self._index = (self._index + 1) % len(self._buttons)
                self._play("move")
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._play("select")
                self._buttons[self._index].activate()
                return True
        elif event.type == pygame.MOUSEMOTION:
            for i, button in enumerate(self._buttons):
                if button.rect.collidepoint(event.pos) and i != self._index:
                    self._index = i
                    self._play("move")
                    return True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, button in enumerate(self._buttons):
                if button.rect.collidepoint(event.pos):
                    self._index = i
                    self._play("select")
                    button.activate()
                    return True
        return False

    def draw(self, surface, fonts):
        for i, button in enumerate(self._buttons):
            button.draw(surface, fonts, i == self._index)


class TextInput:
    """A small, safe text box: only letters, digits, spaces, - and _; length-limited."""

    def __init__(self, rect, max_length=12, text=""):
        self._rect = pygame.Rect(rect)
        self._max = max_length
        self._text = ""
        self._error = ""
        self._error_timer = 0.0
        for ch in text:
            self._add_char(ch)

    @property
    def text(self):
        return self._text

    @property
    def rect(self):
        return self._rect

    def _add_char(self, ch):
        if not (ch.isalnum() or ch in " -_") or not ch.isprintable():
            self._show_error("Only letters, numbers, space, - and _")
            return
        if len(self._text) >= self._max:
            self._show_error(f"Max {self._max} characters")
            return
        self._text += ch

    def _show_error(self, message):
        self._error = message
        self._error_timer = 1.6

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self._text = self._text[:-1]
                return True
            if event.unicode and event.key not in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE,
                                                   pygame.K_TAB):
                for ch in event.unicode:
                    self._add_char(ch)
                return True
        return False

    def update(self, dt):
        self._error_timer = max(0.0, self._error_timer - dt)

    def draw(self, surface, fonts, active=True):
        draw_panel(surface, self._rect, (18, 18, 34), ACCENT if active else PANEL_LIGHT, radius=10)
        cursor = "|" if active and pygame.time.get_ticks() // 450 % 2 == 0 else " "
        shown = self._text + cursor if self._text or active else "Player"
        draw_text(surface, shown, fonts.get(26), WHITE if self._text else GREY,
                  (self._rect.left + 14, self._rect.centery), "midleft", shadow=False)
        if self._error_timer > 0:
            draw_text(surface, self._error, fonts.get(16), (255, 120, 120),
                      (self._rect.centerx, self._rect.bottom + 6), "midtop")


# --------------------------------------------------------------------------
# HUD
# --------------------------------------------------------------------------
def format_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def draw_cooldown_ring(surface, center, radius, ratio, color):
    """Radial sweep that fills clockwise as an ability recharges."""
    if ratio >= 1:
        pygame.draw.circle(surface, color, center, radius, 3)
        return
    pygame.draw.circle(surface, (40, 40, 60), center, radius, 3)
    rect = pygame.Rect(0, 0, radius * 2, radius * 2)
    rect.center = center
    start = math.pi / 2
    end = start + max(0.05, ratio) * math.tau
    pygame.draw.arc(surface, color, rect, start, end, 3)


class HUD:
    def __init__(self, fonts):
        self._fonts = fonts

    def draw(self, surface, world, fps=None):
        fonts = self._fonts
        player = world.player
        # XP bar across the very top
        xp_rect = pygame.Rect(0, 0, SCREEN_W, 12)
        draw_bar(surface, xp_rect, player.xp / max(1, player.xp_to_next), XP_BLUE, (14, 20, 40), border=False, radius=0)
        # health + level panel
        panel = pygame.Rect(14, 22, 330, 64)
        draw_panel(surface, panel, alpha=200)
        draw_text(surface, f"LV {player.level}", fonts.get(26, bold=True), GOLD, (panel.left + 14, panel.top + 8))
        hp_rect = pygame.Rect(panel.left + 90, panel.top + 14, 222, 18)
        draw_bar(surface, hp_rect, player.hp / player.stats.max_hp, HP_RED)
        draw_text(surface, f"{int(math.ceil(player.hp))} / {int(player.stats.max_hp)}", fonts.get(14, bold=True),
                  WHITE, hp_rect.center, "center")
        draw_text(surface, f"XP {player.xp}/{player.xp_to_next}", fonts.get(14), (170, 200, 230),
                  (panel.left + 90, panel.top + 38), shadow=False)
        # timer and kills
        draw_text(surface, format_time(world.time), fonts.get(40, bold=True), WHITE, (SCREEN_W / 2, 16), "midtop")
        kills = draw_text(surface, f"{world.kills} kills", fonts.get(18), (210, 210, 225),
                          (SCREEN_W - 20, 24), "topright")
        if fps is not None:
            draw_text(surface, f"{fps:.0f} FPS", fonts.get(14), GREY, (SCREEN_W - 20, kills.bottom + 2), "topright")
        boss = world.boss
        if boss is not None:
            self._boss_bar(surface, boss)
        else:
            remaining = world.director.time_to_boss - world.time
            if 0 < remaining < 30:
                draw_text(surface, f"Boss in {int(remaining) + 1}s", fonts.get(18, bold=True), (255, 110, 120),
                          (SCREEN_W / 2, 62), "midtop")
        self._elements_panel(surface, player)
        self._fusions_panel(surface, player)

    def _boss_bar(self, surface, boss):
        rect = pygame.Rect(0, 0, 560, 18)
        rect.midtop = (SCREEN_W / 2, 74)
        draw_text(surface, boss.name.upper(), self._fonts.get(16, bold=True), (255, 160, 200),
                  (rect.centerx, rect.top - 18), "midtop")
        draw_bar(surface, rect, boss.hp_ratio, (210, 50, 120) if not boss.enraged else (255, 60, 60))

    def _elements_panel(self, surface, player):
        elements = player.elements
        size = 52
        panel = pygame.Rect(14, SCREEN_H - 84, 22 + len(elements) * (size + 10), 72)
        draw_panel(surface, panel, alpha=200)
        for i, element in enumerate(elements):
            cx = panel.left + 16 + size // 2 + i * (size + 10)
            cy = panel.top + 30
            draw_cooldown_ring(surface, (cx, cy), 23, element.cooldown_ratio, element.color)
            draw_element_icon(surface, element.element_id, (cx, cy), 14, glow=False)
            # level pips
            for lv in range(8):
                color = element.color if lv < element.level else (50, 50, 70)
                pygame.draw.rect(surface, color, (cx - 24 + lv * 6, cy + 30, 5, 5))

    def _fusions_panel(self, surface, player):
        fusions = player.fusions
        if not fusions:
            return
        size = 52
        width = 22 + len(fusions) * (size + 10)
        panel = pygame.Rect(SCREEN_W - 14 - width, SCREEN_H - 84, width, 72)
        draw_panel(surface, panel, alpha=200, border=GOLD)
        for i, fusion in enumerate(fusions):
            cx = panel.left + 16 + size // 2 + i * (size + 10)
            cy = panel.top + 30
            ready = fusion.cooldown_ratio
            draw_fusion_icon(surface, fusion.fusion_id, (cx, cy), 18)
            draw_cooldown_ring(surface, (cx, cy), 24, ready, fusion.color)
            draw_text(surface, f"{fusion.level}", self._fonts.get(13, bold=True), WHITE, (cx, cy + 27), "midtop")


# --------------------------------------------------------------------------
# Upgrade card
# --------------------------------------------------------------------------
CATEGORY_LABEL = {"basic": "STAT", "element": "ELEMENT", "fusion": "FUSION"}


def draw_upgrade_card(surface, fonts, rect, upgrade, hovered, index, t):
    rarity = upgrade.rarity
    lift = -10 if hovered else 0
    rect = rect.move(0, lift)
    if hovered or rarity.rank >= 2:
        pulse = 0.6 + 0.4 * math.sin(t * 4)
        draw_panel(surface, rect.inflate(16, 16), scale_color(rarity.color, 0.4 * pulse), rarity.color,
                   alpha=110, radius=20, width=0)
    draw_panel(surface, rect, (24, 24, 44), rarity.color if hovered else scale_color(rarity.color, 0.7),
               alpha=250, radius=16, width=3)
    # header stripe in the upgrade's element colour
    stripe = pygame.Rect(rect.left + 3, rect.top + 3, rect.width - 6, 8)
    pygame.draw.rect(surface, upgrade.color, stripe, border_radius=6)
    draw_text(surface, rarity.name.upper(), fonts.get(16, bold=True), rarity.color,
              (rect.centerx, rect.top + 20), "midtop")
    draw_text(surface, CATEGORY_LABEL.get(upgrade.category, ""), fonts.get(13), GREY,
              (rect.centerx, rect.top + 42), "midtop", shadow=False)
    draw_upgrade_icon(surface, upgrade, (rect.centerx, rect.top + 120), 38)
    title_rect = pygame.Rect(rect.left + 16, rect.top + 182, rect.width - 32, 70)
    y = draw_wrapped(surface, upgrade.title(), fonts.get(22, bold=True), WHITE, title_rect, anchor_center=True)
    desc_rect = pygame.Rect(rect.left + 20, y + 10, rect.width - 40, 150)
    draw_wrapped(surface, upgrade.description(), fonts.get(17), (205, 205, 220), desc_rect, anchor_center=True)
    draw_text(surface, f"[{index + 1}]", fonts.get(18, bold=True), GREY, (rect.centerx, rect.bottom - 30), "midtop")
    return rect
