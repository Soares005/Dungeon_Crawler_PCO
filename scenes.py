"""Game screens, organised as a state machine (a stack of Scenes).

Scene is the abstract base class: every screen overrides handle_event(),
update() and draw(). The Game object only talks to "the scene on top of the
stack", so adding a new screen never requires changing the main loop.
Overlay scenes (pause, level-up) are drawn on top of the scene below them.
"""
import math
import random
from abc import ABC, abstractmethod

import pygame

from settings import (SCREEN_W, SCREEN_H, WHITE, GREY, GOLD, ACCENT, PANEL, PANEL_LIGHT,
                      ELEMENT_IDS, ELEMENT_COLORS)
from elements import ELEMENT_CLASSES
from fusions import FUSION_RECIPES, FUSIONS_BY_ID
from reactions import ALL_REACTIONS, REACTIONS_BY_ID
from upgrades import UpgradePool
from world import World
from renderer import WorldRenderer, Camera
from particles import EffectsDirector
from save_manager import RunRecord, MAX_NAME_LENGTH
from gfx import blit_glow, scale_color
from ui import (Menu, TextInput, HUD, draw_text, draw_wrapped, draw_panel, dim_screen, draw_bar,
                draw_element_icon, draw_fusion_icon, draw_upgrade_card, format_time)


class Scene(ABC):
    overlay = False          # True: the scene below is drawn first (pause, level-up)

    def __init__(self, game):
        self._game = game

    def on_resume(self):
        """Called when the scene above this one is closed."""

    @abstractmethod
    def handle_event(self, event):
        ...

    def update(self, dt):
        pass

    @abstractmethod
    def draw(self, surface):
        ...


# --------------------------------------------------------------------------
# Shared animated background for menus
# --------------------------------------------------------------------------
class MenuBackdrop:
    def __init__(self, count=46):
        rng = random.Random(3)
        self._orbs = [[rng.uniform(0, SCREEN_W), rng.uniform(0, SCREEN_H), rng.uniform(-18, 18),
                       rng.uniform(-30, -8), rng.uniform(3, 7), rng.choice(ELEMENT_IDS)] for _ in range(count)]
        self._time = 0.0

    def update(self, dt):
        self._time += dt
        for orb in self._orbs:
            orb[0] = (orb[0] + orb[2] * dt) % SCREEN_W
            orb[1] = (orb[1] + orb[3] * dt) % SCREEN_H

    def draw(self, surface):
        surface.fill((12, 12, 26))
        for i in range(0, SCREEN_W, 80):
            pygame.draw.line(surface, (20, 22, 40), (i, 0), (i, SCREEN_H))
        for j in range(0, SCREEN_H, 80):
            pygame.draw.line(surface, (20, 22, 40), (0, j), (SCREEN_W, j))
        for x, y, _, _, size, element in self._orbs:
            color = ELEMENT_COLORS[element]
            blit_glow(surface, (x, y), size * 4, scale_color(color, 0.5))
            pygame.draw.circle(surface, color, (int(x), int(y)), int(size * 0.6))


def draw_title(surface, fonts, text, y, size=64, color=WHITE, glow_color=ACCENT):
    blit_glow(surface, (SCREEN_W / 2, y + size / 2), size * 3, scale_color(glow_color, 0.35))
    draw_text(surface, text, fonts.get(size, bold=True), color, (SCREEN_W / 2, y), "midtop")


def back_pressed(event):
    return event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE)


# --------------------------------------------------------------------------
# Main menu
# --------------------------------------------------------------------------
class MainMenuScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self._backdrop = MenuBackdrop()
        self._time = 0.0
        self._menu = Menu([
            ("Play", lambda: game.push(ElementSelectScene(game))),
            ("Elemental Codex", lambda: game.push(CodexScene(game))),
            ("Hall of Fame", lambda: game.push(HallOfFameScene(game))),
            ("How to Play", lambda: game.push(HowToPlayScene(game))),
            ("Settings", lambda: game.push(SettingsScene(game))),
            ("Quit", game.quit),
        ], SCREEN_W // 2, 270, audio=game.audio)

    def handle_event(self, event):
        self._menu.handle_event(event)

    def update(self, dt):
        self._time += dt
        self._backdrop.update(dt)

    def draw(self, surface):
        fonts = self._game.fonts
        self._backdrop.draw(surface)
        # title: each letter of "ELEMENTAL" cycles through the element colours
        title = "ELEMENTAL"
        font = fonts.get(84, bold=True)
        widths = [font.size(ch)[0] for ch in title]
        x = SCREEN_W / 2 - sum(widths) / 2
        blit_glow(surface, (SCREEN_W / 2, 120), 300, (60, 40, 110))
        for i, ch in enumerate(title):
            element = ELEMENT_IDS[(i + int(self._time * 2)) % len(ELEMENT_IDS)]
            bob = math.sin(self._time * 3 + i * 0.5) * 4
            draw_text(surface, ch, font, ELEMENT_COLORS[element], (x, 60 + bob))
            x += widths[i]
        draw_text(surface, "CHAOS", fonts.get(56, bold=True), WHITE, (SCREEN_W / 2, 150), "midtop")
        draw_text(surface, "Combine elements.  Trigger reactions.  Survive.", fonts.get(20), GREY,
                  (SCREEN_W / 2, 222), "midtop")
        self._menu.draw(surface, fonts)
        save = self._game.save
        progress = (f"Fusions discovered {len(save.discovered_fusions)}/{len(FUSION_RECIPES)}"
                    f"   ·   Reactions {len(save.discovered_reactions)}/{len(ALL_REACTIONS)}"
                    f"   ·   Runs {save.total_runs}")
        draw_text(surface, progress, fonts.get(18), (190, 190, 210), (SCREEN_W / 2, SCREEN_H - 40), "midtop")
        if save.last_error:
            draw_text(surface, save.last_error, fonts.get(16), (255, 140, 140), (SCREEN_W / 2, SCREEN_H - 66), "midtop")
        draw_text(surface, "Arrows/W-S + Enter or mouse", fonts.get(14), (110, 110, 140), (16, SCREEN_H - 26))


# --------------------------------------------------------------------------
# Starting element selection
# --------------------------------------------------------------------------
class ElementSelectScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self._backdrop = MenuBackdrop()
        self._options = list(ELEMENT_IDS) + ["random"]
        self._index = 0
        self._rects = []
        card_w, card_h, gap = 160, 300, 14
        total = len(self._options) * card_w + (len(self._options) - 1) * gap
        left = (SCREEN_W - total) // 2
        for i in range(len(self._options)):
            self._rects.append(pygame.Rect(left + i * (card_w + gap), 200, card_w, card_h))
        self._time = 0.0

    def _choose(self, index):
        option = self._options[index]
        if option == "random":
            option = random.choice(ELEMENT_IDS)
        self._game.audio.play("select")
        self._game.reset(PlayScene(self._game, option))

    def handle_event(self, event):
        if back_pressed(event):
            self._game.pop()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._index = (self._index - 1) % len(self._options)
                self._game.audio.play("move", 0.6)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._index = (self._index + 1) % len(self._options)
                self._game.audio.play("move", 0.6)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self._choose(self._index)
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    self._index = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    self._choose(i)

    def update(self, dt):
        self._time += dt
        self._backdrop.update(dt)

    def draw(self, surface):
        fonts = self._game.fonts
        self._backdrop.draw(surface)
        draw_title(surface, fonts, "CHOOSE YOUR FIRST ELEMENT", 70, 48)
        draw_text(surface, "Every other element is unlocked by levelling up during the run.", fonts.get(20), GREY,
                  (SCREEN_W / 2, 135), "midtop")
        for i, (option, rect) in enumerate(zip(self._options, self._rects)):
            selected = i == self._index
            card = rect.move(0, -12 if selected else 0)
            color = ELEMENT_COLORS.get(option, GOLD)
            draw_panel(surface, card, (24, 24, 44), color if selected else PANEL_LIGHT, radius=14,
                       width=3 if selected else 2)
            if option == "random":
                draw_text(surface, "?", fonts.get(64, bold=True), GOLD, (card.centerx, card.top + 40), "midtop")
                draw_text(surface, "Random", fonts.get(24, bold=True), WHITE, (card.centerx, card.top + 140), "midtop")
                draw_wrapped(surface, "Let chaos decide.", fonts.get(16), GREY,
                             pygame.Rect(card.left + 12, card.top + 180, card.width - 24, 100), anchor_center=True)
                continue
            cls = ELEMENT_CLASSES[option]
            draw_element_icon(surface, option, (card.centerx, card.top + 80), 30 if selected else 26)
            draw_text(surface, cls.name, fonts.get(24, bold=True), color, (card.centerx, card.top + 140), "midtop")
            draw_text(surface, cls.attack_name, fonts.get(16, bold=True), WHITE, (card.centerx, card.top + 174), "midtop")
            draw_wrapped(surface, cls.effect_text, fonts.get(15), (200, 200, 215),
                         pygame.Rect(card.left + 12, card.top + 202, card.width - 24, 90), anchor_center=True)
        draw_text(surface, "Left/Right to choose · Enter to start · Esc to go back", fonts.get(18), GREY,
                  (SCREEN_W / 2, SCREEN_H - 60), "midtop")


# --------------------------------------------------------------------------
# Gameplay
# --------------------------------------------------------------------------
MOVE_KEYS = {
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1),
    pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0),
    pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
}


class PlayScene(Scene):
    def __init__(self, game, starting_element):
        super().__init__(game)
        save = game.save
        self._starting_element = starting_element
        self._world = World(starting_element, save.discovered_fusions, save.discovered_reactions)
        self._renderer = WorldRenderer()
        self._camera = Camera()
        self._camera.snap(self._world.player.pos)
        self._camera.set_shake_enabled(game.settings.screen_shake)
        self._effects = EffectsDirector(game.fonts, game.audio, game.settings)
        self._hud = HUD(game.fonts)
        self._pool = UpgradePool(random.Random())
        self._death_timer = None
        self._new_discoveries = []
        self._last_dt = 0.0
        save.count_run()
        save.save()

    @property
    def world(self):
        return self._world

    @property
    def pool(self):
        return self._pool

    @property
    def starting_element(self):
        return self._starting_element

    def apply_upgrade(self, upgrade, is_reward):
        upgrade.apply(self._world.player, self._world)
        if is_reward:
            self._world.consume_reward()
        else:
            self._world.consume_level_up()

    def on_resume(self):
        # settings may have changed in the pause menu
        self._camera.set_shake_enabled(self._game.settings.screen_shake)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_p):
            if self._death_timer is None:
                self._game.push(PauseScene(self._game, self))
        elif event.type == pygame.WINDOWFOCUSLOST and self._death_timer is None:
            self._game.push(PauseScene(self._game, self))      # auto-pause when alt-tabbing

    def _read_movement(self):
        pressed = pygame.key.get_pressed()
        x = y = 0
        for key, (dx, dy) in MOVE_KEYS.items():
            if pressed[key]:
                x += dx
                y += dy
        return (max(-1, min(1, x)), max(-1, min(1, y)))

    def update(self, dt):
        world = self._world
        if self._death_timer is None:
            world.update(dt, self._read_movement())
        else:
            self._death_timer -= dt
        self._effects.handle_events(world.events.drain(), self._camera)
        found = world.drain_discoveries()
        if found:
            for kind, item_id in found:
                if self._game.save.discover(kind, item_id):
                    self._new_discoveries.append((kind, item_id))
            self._game.save.save()
        self._camera.follow(world.player.pos, dt)
        self._camera.update(dt)
        self._effects.emit_status_particles(world, self._camera.view_rect)
        self._effects.update(dt)
        self._last_dt = dt

        if world.game_over and self._death_timer is None:
            self._death_timer = 2.0
        elif self._death_timer is not None:
            if self._death_timer <= 0:
                self._game.switch(GameOverScene(self._game, world.summary(), self._new_discoveries,
                                                self._starting_element))
        elif world.pending_rewards:
            self._game.push(LevelUpScene(self._game, self, is_reward=True))
        elif world.pending_level_ups:
            self._game.push(LevelUpScene(self._game, self, is_reward=False))

    def draw(self, surface):
        self._renderer.draw(surface, self._world, self._camera, self._effects, self._last_dt)
        self._last_dt = 0.0
        fps = self._game.fps if self._game.settings.show_fps else None
        self._hud.draw(surface, self._world, fps)
        self._effects.draw_screen_effects(surface)


class LevelUpScene(Scene):
    overlay = True
    INPUT_DELAY = 0.35        # ignore keys briefly so a held movement key can't pick a card

    def __init__(self, game, play_scene, is_reward=False):
        super().__init__(game)
        self._play = play_scene
        self._reward = is_reward
        world = play_scene.world
        self._choices = play_scene.pool.roll(world.player, 3, min_rank=2 if is_reward else 0)
        self._index = 0
        self._time = 0.0
        self._rects = []
        width, height, gap = 300, 400, 34
        left = SCREEN_W // 2 - (3 * width + 2 * gap) // 2
        for i in range(len(self._choices)):
            self._rects.append(pygame.Rect(left + i * (width + gap), 190, width, height))
        game.audio.play("level_up" if not is_reward else "unlock", 0.5, 0.2)

    def _pick(self, index):
        if self._time < self.INPUT_DELAY or not 0 <= index < len(self._choices):
            return
        self._game.audio.play("select")
        self._play.apply_upgrade(self._choices[index], self._reward)
        self._game.pop()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_1, pygame.K_KP1):
                self._pick(0)
            elif event.key in (pygame.K_2, pygame.K_KP2):
                self._pick(1)
            elif event.key in (pygame.K_3, pygame.K_KP3):
                self._pick(2)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self._index = (self._index - 1) % len(self._choices)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._index = (self._index + 1) % len(self._choices)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self._pick(self._index)
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    self._index = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    self._pick(i)

    def update(self, dt):
        self._time += dt

    def draw(self, surface):
        fonts = self._game.fonts
        dim_screen(surface, 170)
        appear = min(1.0, self._time / 0.25)
        if self._reward:
            draw_title(surface, fonts, "ELEMENTAL CORE", 60, 54, GOLD, GOLD)
            subtitle = "The boss dropped its core. Choose a powerful reward!"
        else:
            draw_title(surface, fonts, "LEVEL UP!", 60, 58, (255, 230, 120), (255, 200, 80))
            subtitle = f"Level {self._play.world.player.level} - choose one upgrade"
        draw_text(surface, subtitle, fonts.get(22), (220, 220, 235), (SCREEN_W / 2, 132), "midtop")
        for i, (upgrade, rect) in enumerate(zip(self._choices, self._rects)):
            slide = int((1 - appear) * (80 + i * 40))
            draw_upgrade_card(surface, fonts, rect.move(0, slide), upgrade, i == self._index, i, self._time)
        self._draw_build(surface)
        hint = "1 / 2 / 3, arrows + Enter, or click a card"
        draw_text(surface, hint, fonts.get(16), GREY, (SCREEN_W / 2, SCREEN_H - 34), "midtop")

    def _draw_build(self, surface):
        player = self._play.world.player
        y = SCREEN_H - 96
        items = [("e", e) for e in player.elements] + [("f", f) for f in player.fusions]
        x = SCREEN_W / 2 - (len(items) * 56) / 2 + 28
        for kind, item in items:
            if kind == "e":
                draw_element_icon(surface, item.element_id, (x, y), 15)
            else:
                draw_fusion_icon(surface, item.fusion_id, (x, y), 18)
            draw_text(surface, str(item.level), self._game.fonts.get(14, bold=True), WHITE, (x, y + 22), "midtop")
            x += 56


class PauseScene(Scene):
    overlay = True

    def __init__(self, game, play_scene):
        super().__init__(game)
        self._play = play_scene
        self._menu = Menu([
            ("Resume", game.pop),
            ("Restart", self._restart),
            ("Elemental Codex", lambda: game.push(CodexScene(game))),
            ("Settings", lambda: game.push(SettingsScene(game))),
            ("Main Menu", lambda: game.reset(MainMenuScene(game))),
        ], 300, 230, width=300, audio=game.audio)

    def _restart(self):
        self._game.reset(PlayScene(self._game, self._play.starting_element))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_p):
            self._game.pop()
        else:
            self._menu.handle_event(event)

    def draw(self, surface):
        fonts = self._game.fonts
        dim_screen(surface, 175)
        draw_text(surface, "PAUSED", fonts.get(60, bold=True), WHITE, (300, 120), "midtop")
        self._menu.draw(surface, fonts)
        # build overview on the right
        world = self._play.world
        player = world.player
        panel = pygame.Rect(520, 110, 720, 500)
        draw_panel(surface, panel)
        draw_text(surface, "CURRENT BUILD", fonts.get(24, bold=True), GOLD, (panel.left + 24, panel.top + 18))
        # column 1: elements, column 2: fusions, column 3: stats
        y = panel.top + 64
        for element in player.elements:
            draw_element_icon(surface, element.element_id, (panel.left + 40, y + 12), 13)
            draw_text(surface, f"{ELEMENT_CLASSES[element.element_id].name}  Lv {element.level}",
                      fonts.get(18, bold=True), element.color, (panel.left + 64, y))
            y += 36
        y = panel.top + 64
        if not player.fusions:
            draw_text(surface, "No fusions yet", fonts.get(17), GREY, (panel.left + 236, y), shadow=False)
        for fusion in player.fusions:
            draw_fusion_icon(surface, fusion.fusion_id, (panel.left + 250, y + 12), 14)
            draw_text(surface, f"{fusion.name}  Lv {fusion.level}", fonts.get(17, bold=True), fusion.color,
                      (panel.left + 272, y))
            y += 36
        stats = player.stats
        lines = [
            f"Damage x{stats.damage_mult:.2f}", f"Attack speed x{stats.attack_speed:.2f}",
            f"Move speed {stats.move_speed:.0f}", f"Projectile size x{stats.projectile_size:.2f}",
            f"Extra projectiles +{stats.extra_projectiles}", f"Pickup radius {stats.pickup_radius:.0f}",
            f"Max HP {stats.max_hp:.0f}", f"Regen {stats.regen:.1f}/s",
        ]
        for i, line in enumerate(lines):
            draw_text(surface, line, fonts.get(16), (200, 200, 220),
                      (panel.right - 190, panel.top + 64 + i * 30), shadow=False)
        draw_text(surface, f"Time {format_time(world.time)}   Kills {world.kills}", fonts.get(18), GREY,
                  (panel.left + 24, panel.bottom - 40), shadow=False)


class GameOverScene(Scene):
    def __init__(self, game, summary, discoveries, starting_element):
        super().__init__(game)
        self._summary = summary
        self._discoveries = discoveries
        self._starting_element = starting_element
        self._saved = False
        self._rank = None
        self._qualifies = game.save.qualifies(summary["time"], summary["kills"])
        self._input = TextInput(pygame.Rect(SCREEN_W // 2 - 160, 560, 320, 46), MAX_NAME_LENGTH)
        self._menu = Menu([
            ("Play Again", self._restart),
            ("Main Menu", self._main_menu),
        ], SCREEN_W // 2, 0, width=240, height=46)
        # place the two buttons side by side under the name box
        buttons = self._menu.buttons
        buttons[0].rect.topleft = (SCREEN_W // 2 - 250, 636)
        buttons[1].rect.topleft = (SCREEN_W // 2 + 10, 636)
        self._time = 0.0
        self._backdrop = MenuBackdrop(30)

    def _commit(self):
        """Save the run once (with whatever name was typed)."""
        if self._saved:
            return
        self._saved = True
        s = self._summary
        record = RunRecord(self._input.text, s["time"], s["kills"], s["level"], s["fusions"])
        self._rank = self._game.save.add_record(record)
        self._game.save.save()

    def _restart(self):
        self._commit()
        self._game.reset(PlayScene(self._game, self._starting_element))

    def _main_menu(self):
        self._commit()
        self._game.reset(MainMenuScene(self._game))

    def handle_event(self, event):
        if self._input.handle_event(event):
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            fake = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN if event.key == pygame.K_RIGHT else pygame.K_UP)
            self._menu.handle_event(fake)
            return
        self._menu.handle_event(event)

    def update(self, dt):
        self._time += dt
        self._input.update(dt)
        self._backdrop.update(dt)

    def draw(self, surface):
        fonts = self._game.fonts
        s = self._summary
        self._backdrop.draw(surface)
        dim_screen(surface, 120)
        draw_title(surface, fonts, "YOU FELL TO THE CHAOS", 30, 52, (255, 120, 130), (200, 40, 60))
        # main stats
        stats = [("Survived", format_time(s["time"])), ("Enemies", str(s["kills"])),
                 ("Level", str(s["level"])), ("Bosses", str(s["bosses"]))]
        for i, (label, value) in enumerate(stats):
            rect = pygame.Rect(0, 0, 210, 92)
            rect.topleft = (SCREEN_W // 2 - 450 + i * 230, 108)
            draw_panel(surface, rect)
            draw_text(surface, value, fonts.get(36, bold=True), WHITE, (rect.centerx, rect.top + 10), "midtop")
            draw_text(surface, label, fonts.get(16), GREY, (rect.centerx, rect.top + 60), "midtop")
        # elements and fusions of this run
        panel = pygame.Rect(SCREEN_W // 2 - 450, 218, 440, 300)
        draw_panel(surface, panel)
        draw_text(surface, "ELEMENTS UNLOCKED", fonts.get(18, bold=True), GOLD, (panel.left + 20, panel.top + 14))
        for i, (element_id, level) in enumerate(s["elements"]):
            x = panel.left + 50 + (i % 3) * 130
            y = panel.top + 70 + (i // 3) * 64
            draw_element_icon(surface, element_id, (x, y), 16)
            draw_text(surface, f"{ELEMENT_CLASSES[element_id].name} {level}", fonts.get(17, bold=True),
                      ELEMENT_COLORS[element_id], (x + 24, y - 11))
        draw_text(surface, "FUSIONS", fonts.get(18, bold=True), GOLD, (panel.left + 20, panel.top + 196))
        if s["fusions"]:
            for i, fusion_id in enumerate(s["fusions"][:10]):
                x = panel.left + 38 + i * 41
                draw_fusion_icon(surface, fusion_id, (x, panel.top + 250), 16)
        else:
            draw_text(surface, "None this run - try owning two elements at level 2!", fonts.get(16), GREY,
                      (panel.left + 20, panel.top + 232), shadow=False)
        # reactions and discoveries
        panel2 = pygame.Rect(SCREEN_W // 2 + 10, 218, 440, 300)
        draw_panel(surface, panel2)
        draw_text(surface, "REACTIONS TRIGGERED", fonts.get(18, bold=True), GOLD, (panel2.left + 20, panel2.top + 14))
        reactions = sorted(s["reactions"].items(), key=lambda kv: -kv[1])
        if not reactions:
            draw_text(surface, "None - mix elements to cause reactions!", fonts.get(16), GREY,
                      (panel2.left + 20, panel2.top + 52), shadow=False)
        for i, (reaction_id, count) in enumerate(reactions[:5]):
            reaction = REACTIONS_BY_ID[reaction_id]
            draw_text(surface, f"{reaction.name}", fonts.get(18, bold=True), reaction.color,
                      (panel2.left + 20, panel2.top + 50 + i * 30))
            draw_text(surface, f"x{count}", fonts.get(18), WHITE, (panel2.right - 24, panel2.top + 50 + i * 30),
                      "topright")
        if self._discoveries:
            names = []
            for kind, item_id in self._discoveries:
                names.append(FUSIONS_BY_ID[item_id].name if kind == "fusion" else REACTIONS_BY_ID[item_id].name)
            draw_text(surface, "NEW IN THE CODEX", fonts.get(16, bold=True), (140, 255, 170),
                      (panel2.left + 20, panel2.top + 212))
            draw_wrapped(surface, ", ".join(names), fonts.get(15), WHITE,
                         pygame.Rect(panel2.left + 20, panel2.top + 236, panel2.width - 40, 60))
        # name entry
        if self._saved and self._rank:
            label = f"Saved to the Hall of Fame - rank #{self._rank}"
        elif self._qualifies:
            label = "New Hall of Fame entry! Type your name:"
        else:
            label = "Type your name for the records:"
        draw_text(surface, label, fonts.get(18, bold=True), GOLD if self._qualifies else GREY,
                  (SCREEN_W // 2, 532), "midtop")
        self._input.draw(surface, fonts, active=not self._saved)
        self._menu.draw(surface, fonts)


# --------------------------------------------------------------------------
# Elemental Codex
# --------------------------------------------------------------------------
class CodexScene(Scene):
    TABS = ("Elements", "Fusions", "Reactions")

    def __init__(self, game):
        super().__init__(game)
        self._tab = 1
        self._backdrop = MenuBackdrop(24)
        self._tab_rects = [pygame.Rect(SCREEN_W // 2 - 330 + i * 225, 150, 210, 40) for i in range(3)]

    def handle_event(self, event):
        if back_pressed(event):
            self._game.pop()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                self._tab = (self._tab - 1) % 3
                self._game.audio.play("move", 0.6)
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_e, pygame.K_TAB):
                self._tab = (self._tab + 1) % 3
                self._game.audio.play("move", 0.6)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._tab_rects):
                if rect.collidepoint(event.pos):
                    self._tab = i
                    self._game.audio.play("select", 0.6)

    def update(self, dt):
        self._backdrop.update(dt)

    def draw(self, surface):
        fonts = self._game.fonts
        save = self._game.save
        self._backdrop.draw(surface)
        dim_screen(surface, 110)
        draw_title(surface, fonts, "ELEMENTAL CODEX", 20, 46, WHITE, ACCENT)
        found_f = save.discovered_fusions
        found_r = save.discovered_reactions
        total = len(FUSION_RECIPES) + len(ALL_REACTIONS)
        found = len(found_f) + len(found_r)
        bar = pygame.Rect(SCREEN_W // 2 - 300, 92, 600, 16)
        draw_bar(surface, bar, found / total, ACCENT)
        draw_text(surface, f"Discovery {found}/{total}   ·   Fusions {len(found_f)}/{len(FUSION_RECIPES)}"
                           f"   ·   Reactions {len(found_r)}/{len(ALL_REACTIONS)}",
                  fonts.get(16), (210, 210, 230), (SCREEN_W / 2, 114), "midtop")
        for i, (name, rect) in enumerate(zip(self.TABS, self._tab_rects)):
            active = i == self._tab
            draw_panel(surface, rect, PANEL_LIGHT if active else PANEL, ACCENT if active else PANEL_LIGHT, radius=10)
            draw_text(surface, name, fonts.get(20, bold=active), WHITE if active else GREY, rect.center, "center")
        if self._tab == 0:
            self._draw_elements(surface, fonts, found_f)
        elif self._tab == 1:
            self._draw_fusions(surface, fonts, found_f)
        else:
            self._draw_reactions(surface, fonts, found_r)
        draw_text(surface, "Left/Right or click to change tab · Esc to go back", fonts.get(16), GREY,
                  (SCREEN_W / 2, SCREEN_H - 30), "midtop")

    def _draw_elements(self, surface, fonts, found_fusions):
        for i, element_id in enumerate(ELEMENT_IDS):
            cls = ELEMENT_CLASSES[element_id]
            rect = pygame.Rect(0, 0, 390, 220)
            rect.topleft = (SCREEN_W // 2 - 600 + (i % 3) * 405, 206 + (i // 3) * 235)
            color = ELEMENT_COLORS[element_id]
            draw_panel(surface, rect, border=color)
            draw_element_icon(surface, element_id, (rect.left + 46, rect.top + 50), 24)
            draw_text(surface, cls.name, fonts.get(26, bold=True), color, (rect.left + 90, rect.top + 18))
            draw_text(surface, cls.attack_name, fonts.get(17, bold=True), WHITE, (rect.left + 90, rect.top + 54))
            y = draw_wrapped(surface, cls.effect_text, fonts.get(16), (205, 205, 220),
                             pygame.Rect(rect.left + 20, rect.top + 92, rect.width - 40, 60))
            draw_text(surface, f"Special upgrade: {cls.special_title}", fonts.get(15), GREY,
                      (rect.left + 20, y + 4), shadow=False)
            partners = []
            for recipe in FUSION_RECIPES:
                if element_id in recipe.elements:
                    partners.append(recipe.name if recipe.fusion_id in found_fusions else "???")
            draw_wrapped(surface, "Fusions: " + ", ".join(partners), fonts.get(14), (180, 180, 210),
                         pygame.Rect(rect.left + 20, y + 28, rect.width - 40, 60))

    def _draw_fusions(self, surface, fonts, found_fusions):
        for i, recipe in enumerate(FUSION_RECIPES):
            rect = pygame.Rect(0, 0, 228, 226)
            rect.topleft = (SCREEN_W // 2 - 600 + (i % 5) * 242, 204 + (i // 5) * 238)
            known = recipe.fusion_id in found_fusions
            draw_panel(surface, rect, border=recipe.color if known else PANEL_LIGHT)
            draw_fusion_icon(surface, recipe.fusion_id, (rect.centerx, rect.top + 52), 30, discovered=known)
            if known:
                a, b = sorted(recipe.elements)
                draw_text(surface, recipe.name, fonts.get(20, bold=True), recipe.color,
                          (rect.centerx, rect.top + 96), "midtop")
                draw_text(surface, f"{ELEMENT_CLASSES[a].name} + {ELEMENT_CLASSES[b].name}", fonts.get(15),
                          WHITE, (rect.centerx, rect.top + 124), "midtop")
                draw_wrapped(surface, recipe.description, fonts.get(14), (200, 200, 215),
                             pygame.Rect(rect.left + 14, rect.top + 150, rect.width - 28, 90), anchor_center=True)
            else:
                draw_text(surface, "???", fonts.get(22, bold=True), GREY, (rect.centerx, rect.top + 96), "midtop")
                draw_text(surface, "? + ?", fonts.get(16), GREY, (rect.centerx, rect.top + 128), "midtop")
                draw_wrapped(surface, "Undiscovered. Own two elements at level 2 to find fusions.",
                             fonts.get(14), (130, 130, 160),
                             pygame.Rect(rect.left + 14, rect.top + 158, rect.width - 28, 70), anchor_center=True)

    def _draw_reactions(self, surface, fonts, found_reactions):
        for i, reaction in enumerate(ALL_REACTIONS):
            rect = pygame.Rect(SCREEN_W // 2 - 520, 206 + i * 66, 1040, 58)
            known = reaction.reaction_id in found_reactions
            draw_panel(surface, rect, border=reaction.color if known else PANEL_LIGHT, radius=10)
            if known:
                draw_text(surface, reaction.name, fonts.get(22, bold=True), reaction.color,
                          (rect.left + 20, rect.centery), "midleft")
                combo = f"{reaction.status.title()} + {ELEMENT_CLASSES[reaction.trigger_element].name}"
                draw_text(surface, combo, fonts.get(17, bold=True), WHITE, (rect.left + 230, rect.centery), "midleft")
                draw_text(surface, reaction.description, fonts.get(16), (200, 200, 215),
                          (rect.left + 420, rect.centery), "midleft", shadow=False)
            else:
                draw_text(surface, "???", fonts.get(22, bold=True), GREY, (rect.left + 20, rect.centery), "midleft")
                draw_text(surface, "Undiscovered reaction - hit an enemy that already has a status "
                                   "with a different element.", fonts.get(16), (130, 130, 160),
                          (rect.left + 230, rect.centery), "midleft", shadow=False)


# --------------------------------------------------------------------------
# How to play
# --------------------------------------------------------------------------
HOW_TO_PAGES = (
    ("Controls", [
        "Move with W A S D (or the arrow keys). Attacks are automatic.",
        "Esc or P pauses the game. In menus use arrows + Enter, or the mouse.",
        "On level up, pick a card with 1 / 2 / 3, the arrows + Enter, or a click.",
        "Collect the XP crystals dropped by enemies to level up.",
        "Survive as long as you can. Every 5 minutes a boss arrives - it drops an Elemental Core.",
    ]),
    ("Elements", [
        "Fire - fireballs that explode and set enemies Burning.",
        "Water - piercing bolts that make enemies Wet.",
        "Lightning - instant bolts that chain between enemies and Electrify them.",
        "Ice - a fan of shards that Slow; enough hits Freeze an enemy solid.",
        "Earth - heavy boulders with big damage and knockback.",
        "Wind - fast piercing blades fired in the direction you are moving.",
    ]),
    ("Reactions", [
        "Statuses: Burning, Wet, Frozen, Slowed and Electrified.",
        "Hitting a status with another element causes a REACTION automatically:",
        "Wet + Lightning = Conduction     Burning + Wind = Wildfire",
        "Frozen + Earth = Shatter          Wet + Ice = Flash Freeze",
        "Burning + Water = Steam Burst ... and more to discover in the Codex!",
    ]),
    ("Fusions", [
        "When you own two elements at level 2 or more, their FUSION can appear on a level-up card.",
        "Fusions are powerful new abilities with their own cooldown - Fire Tornado, Meteor Shower, Blizzard...",
        "Your basic elements keep working. You can own many fusions at once and upgrade each one.",
        "Every fusion and reaction you find is saved forever in the Elemental Codex.",
        "Ten fusions exist. Can you discover them all?",
    ]),
)


class HowToPlayScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self._page = 0
        self._backdrop = MenuBackdrop(24)

    def handle_event(self, event):
        if back_pressed(event):
            self._game.pop()
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE):
            self._page = (self._page + 1) % len(HOW_TO_PAGES)
            self._game.audio.play("move", 0.6)
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_LEFT, pygame.K_a):
            self._page = (self._page - 1) % len(HOW_TO_PAGES)
            self._game.audio.play("move", 0.6)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._page = (self._page + 1) % len(HOW_TO_PAGES)

    def update(self, dt):
        self._backdrop.update(dt)

    def draw(self, surface):
        fonts = self._game.fonts
        self._backdrop.draw(surface)
        dim_screen(surface, 110)
        title, lines = HOW_TO_PAGES[self._page]
        draw_title(surface, fonts, "HOW TO PLAY", 40, 46)
        panel = pygame.Rect(SCREEN_W // 2 - 520, 130, 1040, 470)
        draw_panel(surface, panel)
        draw_text(surface, title, fonts.get(34, bold=True), GOLD, (panel.left + 40, panel.top + 26))
        if title == "Elements":
            for i, element_id in enumerate(ELEMENT_IDS):
                draw_element_icon(surface, element_id, (panel.left + 58, panel.top + 110 + i * 56), 16)
        y = panel.top + 96
        for line in lines:
            x = panel.left + (90 if title == "Elements" else 40)
            y = draw_wrapped(surface, line, fonts.get(21), WHITE, pygame.Rect(x, y, panel.width - 130, 80)) + 22
        for i in range(len(HOW_TO_PAGES)):
            color = ACCENT if i == self._page else (70, 70, 100)
            pygame.draw.circle(surface, color, (SCREEN_W // 2 - 45 + i * 30, panel.bottom - 30), 7)
        draw_text(surface, "Left/Right to change page · Esc to go back", fonts.get(16), GREY,
                  (SCREEN_W / 2, SCREEN_H - 50), "midtop")


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
class SettingsScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self._backdrop = MenuBackdrop(24)
        self._menu = Menu([
            ("", self._cycle_volume),
            ("", lambda: self._toggle("screen_shake")),
            ("", lambda: self._toggle("damage_numbers")),
            ("", lambda: self._toggle("show_fps")),
            ("", lambda: self._toggle("fullscreen")),
            ("Back", game.pop),
        ], SCREEN_W // 2, 190, width=460, audio=game.audio)
        self._refresh()

    def _refresh(self):
        s = self._game.settings
        on_off = lambda flag: "On" if flag else "Off"
        labels = [f"Volume:  < {int(round(s.volume * 100))}% >", f"Screen shake:  {on_off(s.screen_shake)}",
                  f"Damage numbers:  {on_off(s.damage_numbers)}", f"Show FPS:  {on_off(s.show_fps)}",
                  f"Fullscreen:  {on_off(s.fullscreen)}"]
        for button, label in zip(self._menu.buttons, labels):
            button.set_label(label)

    def _change_volume(self, delta):
        self._game.settings.change_volume(delta)
        self._apply()

    def _cycle_volume(self):
        """Enter/click on the volume row: +10%, wrapping from 100% back to 0%."""
        settings = self._game.settings
        if settings.volume >= 1.0:
            settings.change_volume(-1.0)
        else:
            settings.change_volume(0.1)
        self._apply()

    def _toggle(self, name):
        self._game.settings.toggle(name)
        self._apply()

    def _apply(self):
        self._game.apply_settings()
        self._game.save.save()
        self._refresh()

    def handle_event(self, event):
        if back_pressed(event):
            self._game.pop()
            return
        if event.type == pygame.KEYDOWN and self._menu.index == 0 and event.key in (
                pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            self._change_volume(-0.1 if event.key in (pygame.K_LEFT, pygame.K_a) else 0.1)
            self._game.audio.play("select")
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and self._menu.index == 0:
            self._change_volume(-0.1)
            return
        self._menu.handle_event(event)

    def update(self, dt):
        self._backdrop.update(dt)

    def draw(self, surface):
        fonts = self._game.fonts
        self._backdrop.draw(surface)
        dim_screen(surface, 110)
        draw_title(surface, fonts, "SETTINGS", 70, 50)
        self._menu.draw(surface, fonts)
        draw_text(surface, "Enter/click toggles · Left/Right change volume (right-click lowers it) · Esc to go back",
                  fonts.get(16), GREY, (SCREEN_W / 2, SCREEN_H - 60), "midtop")


# --------------------------------------------------------------------------
# Hall of Fame
# --------------------------------------------------------------------------
class HallOfFameScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self._backdrop = MenuBackdrop(24)

    def handle_event(self, event):
        if back_pressed(event) or (event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN) \
                or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
            self._game.pop()

    def update(self, dt):
        self._backdrop.update(dt)

    def draw(self, surface):
        fonts = self._game.fonts
        self._backdrop.draw(surface)
        dim_screen(surface, 110)
        draw_title(surface, fonts, "HALL OF FAME", 40, 50, GOLD, GOLD)
        panel = pygame.Rect(SCREEN_W // 2 - 520, 130, 1040, 520)
        draw_panel(surface, panel)
        columns = (("#", 30), ("Name", 90), ("Time", 330), ("Kills", 450), ("Level", 570), ("Fusions", 680),
                   ("Date", 880))
        for title, x in columns:
            draw_text(surface, title, fonts.get(18, bold=True), GOLD, (panel.left + x, panel.top + 20))
        records = self._game.save.records
        if not records:
            draw_text(surface, "No runs yet - go make some chaos!", fonts.get(22), GREY,
                      (panel.centerx, panel.top + 200), "midtop")
        for i, record in enumerate(records):
            y = panel.top + 64 + i * 44
            if i % 2 == 0:
                pygame.draw.rect(surface, (32, 34, 58), (panel.left + 12, y - 6, panel.width - 24, 40), border_radius=8)
            color = (GOLD, (220, 220, 235), (230, 160, 100))[i] if i < 3 else WHITE
            values = (str(i + 1), record.name, format_time(record.time), str(record.kills), str(record.level))
            for (title, x), value in zip(columns, values):
                draw_text(surface, value, fonts.get(20, bold=i < 3), color, (panel.left + x, y), shadow=False)
            for k, fusion_id in enumerate(record.fusions[:6]):
                draw_fusion_icon(surface, fusion_id, (panel.left + 694 + k * 30, y + 13), 12)
            draw_text(surface, record.date, fonts.get(16), GREY, (panel.left + 880, y + 3), shadow=False)
        draw_text(surface, "Esc or click to go back", fonts.get(16), GREY, (SCREEN_W / 2, SCREEN_H - 50), "midtop")
