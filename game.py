"""The Game application: window, main loop and the scene stack (state machine)."""
import math

import pygame

from settings import SCREEN_W, SCREEN_H, FPS, MAX_DT, TITLE, ELEMENT_IDS, ELEMENT_COLORS
from save_manager import SaveManager
from audio import SoundBank
from ui import Fonts
from scenes import MainMenuScene


def make_window_icon():
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(icon, (40, 30, 80), (16, 16), 15)
    for i, element in enumerate(ELEMENT_IDS):
        angle = i * math.tau / len(ELEMENT_IDS)
        pygame.draw.circle(icon, ELEMENT_COLORS[element],
                           (int(16 + math.cos(angle) * 9), int(16 + math.sin(angle) * 9)), 4)
    return icon


class Game:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        self._save = SaveManager()
        self._save.load()
        self._fullscreen = False
        self._screen = self._create_window()
        pygame.display.set_caption(TITLE)
        pygame.display.set_icon(make_window_icon())
        self._clock = pygame.time.Clock()
        self._fonts = Fonts()
        self._audio = SoundBank()
        self._audio.build()
        self._audio.set_volume(self._save.settings.volume)
        self._scenes = []
        self._running = True
        self.push(MainMenuScene(self))

    # -- shared services used by the scenes ---------------------------------------
    @property
    def save(self):
        return self._save

    @property
    def settings(self):
        return self._save.settings

    @property
    def audio(self):
        return self._audio

    @property
    def fonts(self):
        return self._fonts

    @property
    def fps(self):
        return self._clock.get_fps()

    # -- window ----------------------------------------------------------------
    def _create_window(self):
        flags = pygame.SCALED
        if self._save.settings.fullscreen:
            flags |= pygame.FULLSCREEN
        try:
            screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
            self._fullscreen = bool(flags & pygame.FULLSCREEN)
        except pygame.error:
            screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
            self._fullscreen = False
        return screen

    def apply_settings(self):
        """Apply changed settings immediately (volume, fullscreen)."""
        self._audio.set_volume(self.settings.volume)
        if self.settings.fullscreen != self._fullscreen:
            try:
                pygame.display.toggle_fullscreen()
                self._fullscreen = self.settings.fullscreen
            except pygame.error:
                pass

    # -- scene stack -------------------------------------------------------------
    def push(self, scene):
        self._scenes.append(scene)

    def pop(self):
        if len(self._scenes) > 1:
            self._scenes.pop()
            self._scenes[-1].on_resume()
        else:
            self.reset(MainMenuScene(self))

    def switch(self, scene):
        """Replace the top scene."""
        if self._scenes:
            self._scenes.pop()
        self._scenes.append(scene)

    def reset(self, scene):
        """Clear the whole stack and start from `scene`."""
        self._scenes = [scene]

    def quit(self):
        self._running = False

    # -- main loop -----------------------------------------------------------------
    def run(self):
        while self._running:
            # delta time in seconds, clamped so a hiccup can't break the physics
            dt = min(MAX_DT, self._clock.tick(FPS) / 1000.0)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    break
                self._scenes[-1].handle_event(event)
            if not self._running:
                break
            self._scenes[-1].update(dt)
            self._draw()
            pygame.display.flip()
        self._save.save()

    def _draw(self):
        # draw from the last non-overlay scene up to the top
        start = len(self._scenes) - 1
        while start > 0 and self._scenes[start].overlay:
            start -= 1
        for scene in self._scenes[start:]:
            scene.draw(self._screen)
