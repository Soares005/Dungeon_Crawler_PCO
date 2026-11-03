"""Persistent data: Elemental Codex discoveries, best runs and settings.

Everything is stored in one local JSON file (save_data.json). The file is
read when the game starts and written whenever something new is
discovered, a run ends or a setting changes.

Robustness: a missing, unreadable or corrupted file never crashes the game.
Bad files are renamed to save_data.corrupt.json and replaced by defaults,
and every value read from disk is validated before it is used.
"""
import json
import os
import time

from settings import SAVE_FILE
from fusions import FUSIONS_BY_ID
from reactions import REACTIONS_BY_ID

SAVE_VERSION = 1
MAX_RECORDS = 10
MAX_NAME_LENGTH = 12


def clean_name(text):
    """Sanitise a player name typed on the Game Over screen."""
    allowed = "".join(ch for ch in str(text) if ch.isalnum() or ch in " -_")
    allowed = " ".join(allowed.split())[:MAX_NAME_LENGTH]
    return allowed or "Player"


class RunRecord:
    """One finished run, shown in the Hall of Fame."""

    def __init__(self, name, time_survived, kills, level, fusions, date=None):
        self._name = clean_name(name)
        self._time = max(0.0, float(time_survived))
        self._kills = max(0, int(kills))
        self._level = max(1, int(level))
        self._fusions = [f for f in fusions if f in FUSIONS_BY_ID]
        self._date = date or time.strftime("%Y-%m-%d")

    @property
    def name(self):
        return self._name

    @property
    def time(self):
        return self._time

    @property
    def kills(self):
        return self._kills

    @property
    def level(self):
        return self._level

    @property
    def fusions(self):
        return list(self._fusions)

    @property
    def date(self):
        return self._date

    def score(self):
        """Records are ranked by survival time, then kills."""
        return (self._time, self._kills)

    def to_dict(self):
        return {"name": self._name, "time": round(self._time, 2), "kills": self._kills,
                "level": self._level, "fusions": self._fusions, "date": self._date}

    @classmethod
    def from_dict(cls, data):
        """Build a record from JSON data. Raises ValueError/TypeError/KeyError if invalid."""
        if not isinstance(data, dict):
            raise TypeError("record must be an object")
        fusions = data.get("fusions", [])
        if not isinstance(fusions, list):
            fusions = []
        return cls(data["name"], data["time"], data["kills"], data["level"],
                   [str(f) for f in fusions], str(data.get("date", "")) or None)


class GameSettings:
    """User preferences. Values are always kept inside valid ranges."""

    def __init__(self):
        self._volume = 0.6
        self._screen_shake = True
        self._damage_numbers = True
        self._show_fps = False
        self._fullscreen = False

    @property
    def volume(self):
        return self._volume

    @property
    def screen_shake(self):
        return self._screen_shake

    @property
    def damage_numbers(self):
        return self._damage_numbers

    @property
    def show_fps(self):
        return self._show_fps

    @property
    def fullscreen(self):
        return self._fullscreen

    def change_volume(self, delta):
        self._volume = round(min(1.0, max(0.0, self._volume + delta)), 2)

    def toggle(self, name):
        if name == "screen_shake":
            self._screen_shake = not self._screen_shake
        elif name == "damage_numbers":
            self._damage_numbers = not self._damage_numbers
        elif name == "show_fps":
            self._show_fps = not self._show_fps
        elif name == "fullscreen":
            self._fullscreen = not self._fullscreen
        else:
            raise ValueError(f"Unknown setting: {name!r}")

    def to_dict(self):
        return {"volume": self._volume, "screen_shake": self._screen_shake,
                "damage_numbers": self._damage_numbers, "show_fps": self._show_fps,
                "fullscreen": self._fullscreen}

    def load_dict(self, data):
        """Copy valid values from a dict; anything invalid keeps its default."""
        if not isinstance(data, dict):
            return
        volume = data.get("volume")
        if isinstance(volume, (int, float)) and not isinstance(volume, bool):
            self._volume = min(1.0, max(0.0, float(volume)))
        for key in ("screen_shake", "damage_numbers", "show_fps", "fullscreen"):
            if isinstance(data.get(key), bool):
                setattr(self, "_" + key, data[key])


class SaveManager:
    def __init__(self, path=SAVE_FILE):
        self._path = path
        self._fusions = set()
        self._reactions = set()
        self._records = []           # list of RunRecord objects
        self._settings = GameSettings()
        self._total_runs = 0
        self._last_error = ""

    # -- read-only -----------------------------------------------------------
    @property
    def settings(self):
        return self._settings

    @property
    def discovered_fusions(self):
        return set(self._fusions)

    @property
    def discovered_reactions(self):
        return set(self._reactions)

    @property
    def records(self):
        return list(self._records)

    @property
    def total_runs(self):
        return self._total_runs

    @property
    def last_error(self):
        return self._last_error

    # -- changes -----------------------------------------------------------------
    def discover(self, kind, item_id):
        """Mark a fusion/reaction as discovered. Returns True if it was new."""
        if kind == "fusion" and item_id in FUSIONS_BY_ID and item_id not in self._fusions:
            self._fusions.add(item_id)
            return True
        if kind == "reaction" and item_id in REACTIONS_BY_ID and item_id not in self._reactions:
            self._reactions.add(item_id)
            return True
        return False

    def add_record(self, record):
        """Insert a run, keep the best MAX_RECORDS. Returns its rank (1-based) or None."""
        self._records.append(record)
        self._records.sort(key=lambda r: r.score(), reverse=True)
        self._records = self._records[:MAX_RECORDS]
        return self._records.index(record) + 1 if record in self._records else None

    def qualifies(self, time_survived, kills):
        if len(self._records) < MAX_RECORDS:
            return True
        return (time_survived, kills) > self._records[-1].score()

    def count_run(self):
        self._total_runs += 1

    # -- file I/O ----------------------------------------------------------------
    def load(self):
        """Read the save file. Never raises; returns True if a file was loaded."""
        self._last_error = ""
        if not os.path.exists(self._path):
            return False
        try:
            with open(self._path, "r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                raise ValueError("save file root is not an object")
        except (OSError, ValueError, UnicodeDecodeError) as error:
            self._last_error = f"Save file was unreadable and has been reset ({error.__class__.__name__})."
            self._backup_corrupt_file()
            return False

        codex = data.get("codex", {}) if isinstance(data.get("codex"), dict) else {}
        for fusion_id in codex.get("fusions", []) if isinstance(codex.get("fusions"), list) else []:
            self.discover("fusion", fusion_id)
        for reaction_id in codex.get("reactions", []) if isinstance(codex.get("reactions"), list) else []:
            self.discover("reaction", reaction_id)

        self._records = []
        raw_records = data.get("records", [])
        for raw in raw_records if isinstance(raw_records, list) else []:
            try:
                self._records.append(RunRecord.from_dict(raw))
            except (KeyError, TypeError, ValueError):
                continue                    # skip a broken record, keep the rest
        self._records.sort(key=lambda r: r.score(), reverse=True)
        self._records = self._records[:MAX_RECORDS]

        runs = data.get("total_runs", 0)
        self._total_runs = runs if isinstance(runs, int) and runs >= 0 else 0
        self._settings.load_dict(data.get("settings", {}))
        return True

    def save(self):
        """Write the save file atomically. Returns False (and keeps playing) on failure."""
        data = {
            "version": SAVE_VERSION,
            "codex": {"fusions": sorted(self._fusions), "reactions": sorted(self._reactions)},
            "records": [r.to_dict() for r in self._records],
            "total_runs": self._total_runs,
            "settings": self._settings.to_dict(),
        }
        temp_path = str(self._path) + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)
            os.replace(temp_path, self._path)
            return True
        except OSError as error:
            self._last_error = f"Could not save progress ({error.__class__.__name__})."
            return False

    def _backup_corrupt_file(self):
        try:
            os.replace(self._path, str(self._path).replace(".json", "") + ".corrupt.json")
        except OSError:
            pass
