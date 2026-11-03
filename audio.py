"""Procedurally generated sound effects (no external audio files needed).

Every sound is synthesised at start-up from simple waves and noise. If the
computer has no audio device the game simply runs silently.
"""
import math
import random
from array import array

import pygame

SAMPLE_RATE = 22050


class SoundBank:
    def __init__(self):
        self._sounds = {}
        self._enabled = False
        self._volume = 0.6
        self._cooldowns = {}
        self._channels = 1

    @property
    def enabled(self):
        return self._enabled

    def set_volume(self, volume):
        self._volume = min(1.0, max(0.0, float(volume)))

    # ------------------------------------------------------------------
    def build(self):
        """Initialise the mixer and synthesise every sound. Never raises."""
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
            init = pygame.mixer.get_init()
            if init is None or abs(init[1]) != 16:
                return False
            self._rate, _, self._channels = init
            pygame.mixer.set_num_channels(24)
            self._create_sounds()
            self._enabled = True
        except (pygame.error, OSError, ValueError):
            self._enabled = False
        return self._enabled

    def _render(self, duration, generator, volume=0.5, attack=0.004, decay=2.0):
        """Build a pygame Sound from a generator function f(t_seconds, progress)->[-1, 1]."""
        rate = self._rate
        count = max(1, int(rate * duration))
        samples = array("h")
        attack_n = max(1, int(attack * rate))
        for i in range(count):
            progress = i / count
            envelope = min(1.0, i / attack_n) * (1.0 - progress) ** decay
            value = generator(i / rate, progress) * envelope * volume
            sample = int(max(-1.0, min(1.0, value)) * 32000)
            for _ in range(self._channels):
                samples.append(sample)
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def _create_sounds(self):
        rng = random.Random(7)
        tau = math.tau

        def noise(_t, _p):
            return rng.uniform(-1, 1)

        def sweep(f0, f1, wave="sine"):
            state = {"phase": 0.0}

            def gen(_t, p):
                state["phase"] += (f0 + (f1 - f0) * p) / self._rate
                ph = state["phase"] % 1.0
                if wave == "square":
                    return 1.0 if ph < 0.5 else -1.0
                if wave == "saw":
                    return 2 * ph - 1
                if wave == "tri":
                    return 4 * abs(ph - 0.5) - 1
                return math.sin(tau * ph)
            return gen

        def lowpass(gen, amount):
            state = {"y": 0.0}

            def out(t, p):
                state["y"] += amount * (gen(t, p) - state["y"])
                return state["y"] * 1.8
            return out

        def mix(*gens):
            return lambda t, p: sum(g(t, p) for g in gens) / len(gens)

        def arpeggio(freqs, step):
            def gen(t, _p):
                index = min(len(freqs) - 1, int(t / step))
                return math.sin(tau * freqs[index] * t)
            return gen

        r = self._render
        self._sounds = {
            "fire": r(0.22, mix(lowpass(noise, 0.15), sweep(220, 90)), 0.35, decay=1.5),
            "water": r(0.16, sweep(900, 300), 0.25),
            "zap": r(0.18, mix(sweep(1400, 300, "square"), noise), 0.18, decay=1.2),
            "thunder": r(0.55, lowpass(noise, 0.06), 0.6, decay=1.6),
            "ice": r(0.14, mix(sweep(2200, 1700, "tri"), sweep(3300, 2600)), 0.18),
            "rock": r(0.22, mix(lowpass(noise, 0.05), sweep(140, 50)), 0.5),
            "wind": r(0.12, lowpass(noise, 0.35), 0.16, decay=1.0),
            "hit": r(0.05, sweep(500, 200, "square"), 0.10),
            "death": r(0.12, mix(sweep(600, 120, "tri"), lowpass(noise, 0.3)), 0.22),
            "pickup": r(0.07, sweep(1300, 1900), 0.12, decay=1.0),
            "level_up": r(0.6, arpeggio([523, 659, 784, 1046], 0.1), 0.35, decay=1.2),
            "reaction": r(0.3, mix(sweep(700, 1400, "tri"), sweep(1050, 2100)), 0.3),
            "explosion": r(0.45, mix(lowpass(noise, 0.08), sweep(120, 40)), 0.6, decay=1.8),
            "hurt": r(0.2, sweep(220, 110, "saw"), 0.3),
            "boss": r(1.2, mix(sweep(70, 55, "saw"), sweep(105, 82, "saw")), 0.45, attack=0.15, decay=1.0),
            "fusion": r(0.35, mix(sweep(300, 900, "tri"), lowpass(noise, 0.2)), 0.22),
            "unlock": r(0.9, arpeggio([392, 523, 659, 784, 1046, 1318], 0.09), 0.38, decay=0.9),
            "select": r(0.06, sweep(800, 1000, "tri"), 0.2),
            "move": r(0.04, sweep(600, 650, "tri"), 0.12),
            "freeze": r(0.25, mix(sweep(2600, 1200, "tri"), noise), 0.15),
            "heal": r(0.4, arpeggio([659, 880, 1174], 0.1), 0.25),
        }

    # ------------------------------------------------------------------
    def play(self, name, volume=1.0, min_gap=0.05):
        """Play a sound if it exists and wasn't played in the last `min_gap` seconds."""
        if not self._enabled or self._volume <= 0:
            return
        sound = self._sounds.get(name)
        if sound is None:
            return
        now = pygame.time.get_ticks() / 1000.0
        if now - self._cooldowns.get(name, -1.0) < min_gap:
            return
        self._cooldowns[name] = now
        sound.set_volume(min(1.0, self._volume * volume))
        sound.play()
