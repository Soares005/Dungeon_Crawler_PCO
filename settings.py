"""Global constants and balance values for Elemental Chaos.

Everything that a designer might want to tweak lives here, so the rest of the
code never contains "magic numbers" for balance.
"""
from pathlib import Path

# --------------------------------------------------------------------------
# Window / timing
# --------------------------------------------------------------------------
TITLE = "Elemental Chaos"
SCREEN_W = 1280
SCREEN_H = 720
FPS = 60
MAX_DT = 1 / 20          # clamp delta time so a lag spike never teleports things

BASE_DIR = Path(__file__).resolve().parent
SAVE_FILE = BASE_DIR / "save_data.json"
CRASH_LOG = BASE_DIR / "crash.log"

# --------------------------------------------------------------------------
# Arena
# --------------------------------------------------------------------------
ARENA_SIZE = 4000         # square arena, coordinates 0..ARENA_SIZE
GRID_CELL = 96            # spatial hash cell size (pixels)
MAX_ENEMY_RADIUS = 64     # used to widen spatial queries safely

# --------------------------------------------------------------------------
# Colours
# --------------------------------------------------------------------------
BG_COLOR = (16, 18, 32)
BG_GRID = (26, 30, 50)
ARENA_EDGE = (90, 60, 140)
WHITE = (240, 240, 250)
GREY = (140, 145, 165)
DARK = (10, 10, 20)
PANEL = (26, 28, 48)
PANEL_LIGHT = (44, 48, 78)
ACCENT = (160, 120, 255)
HP_RED = (230, 60, 80)
XP_BLUE = (90, 200, 255)
GOLD = (255, 210, 90)

# Element ids are plain strings so they are easy to save in JSON.
FIRE, WATER, LIGHTNING, ICE, EARTH, WIND = "fire", "water", "lightning", "ice", "earth", "wind"
ELEMENT_IDS = (FIRE, WATER, LIGHTNING, ICE, EARTH, WIND)

ELEMENT_COLORS = {
    FIRE: (255, 112, 40),
    WATER: (60, 150, 255),
    LIGHTNING: (255, 232, 80),
    ICE: (150, 232, 255),
    EARTH: (186, 128, 72),
    WIND: (140, 255, 180),
    "neutral": (220, 220, 230),
}

STATUS_COLORS = {
    "burning": (255, 120, 30),
    "wet": (70, 140, 255),
    "frozen": (170, 240, 255),
    "slowed": (120, 200, 255),
    "electrified": (255, 240, 90),
}

# --------------------------------------------------------------------------
# Player
# --------------------------------------------------------------------------
PLAYER_RADIUS = 16
PLAYER_BASE_HP = 100
PLAYER_BASE_SPEED = 215
PLAYER_PICKUP_RADIUS = 90
PLAYER_IFRAMES = 0.45
MAX_ELEMENT_LEVEL = 8
MAX_FUSION_LEVEL = 8
FUSION_MIN_ELEMENT_LEVEL = 2   # both elements must reach this level before fusing
MAX_EXTRA_PROJECTILES = 5

# --------------------------------------------------------------------------
# Enemies / difficulty
# --------------------------------------------------------------------------
MAX_ENEMIES = 320
BOSS_INTERVAL = 300.0     # a boss every 5 minutes
BOSS_WARNING_TIME = 6.0
SPAWN_RING_MIN = 720      # spawn just outside of the screen
SPAWN_RING_MAX = 820
MAX_GEMS = 350

# --------------------------------------------------------------------------
# Rarities: (weight, power multiplier, colour)
# --------------------------------------------------------------------------
RARITY_TABLE = {
    "Common": (62, 1.0, (200, 205, 215)),
    "Rare": (26, 1.5, (80, 170, 255)),
    "Epic": (9, 2.2, (190, 100, 255)),
    "Legendary": (3, 3.2, (255, 190, 60)),
}
RARITY_ORDER = ("Common", "Rare", "Epic", "Legendary")
