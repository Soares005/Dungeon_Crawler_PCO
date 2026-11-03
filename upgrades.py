"""Level-up upgrades, rarities and the pool that rolls three valid choices.

Upgrade is an abstract base class; each kind of upgrade (stat, new element,
element level, element special, fusion unlock, fusion improvement, heal)
is a subclass that overrides title(), description() and apply().
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from settings import RARITY_TABLE, RARITY_ORDER, ELEMENT_COLORS, ELEMENT_IDS, ACCENT
from elements import ELEMENT_CLASSES, element_display_name
from fusions import eligible_recipes


@dataclass(frozen=True)
class Rarity:
    name: str
    weight: int
    power: float
    color: tuple
    rank: int


RARITIES = tuple(Rarity(name, *RARITY_TABLE[name], rank) for rank, name in enumerate(RARITY_ORDER))
RARITY_BY_NAME = {r.name: r for r in RARITIES}


class Upgrade(ABC):
    category = "basic"

    def __init__(self, upgrade_id, rarity):
        self._id = upgrade_id
        self._rarity = rarity

    @property
    def upgrade_id(self):
        return self._id

    @property
    def rarity(self):
        return self._rarity

    @property
    def color(self):
        return ACCENT

    @property
    def icon(self):
        """(kind, key) pair the UI uses to draw an icon."""
        return ("stat", "damage")

    @abstractmethod
    def title(self):
        ...

    @abstractmethod
    def description(self):
        ...

    @abstractmethod
    def apply(self, player, world):
        ...


# --------------------------------------------------------------------------
# Basic stat upgrades
# --------------------------------------------------------------------------
STAT_INFO = {
    # stat: (title, base amount, description template, colour)
    "damage": ("Elemental Power", 0.20, "+{pct}% damage for everything", (255, 120, 120)),
    "move_speed": ("Swift Feet", 0.15, "+{pct}% movement speed", (140, 255, 180)),
    "attack_speed": ("Quick Casting", 0.15, "+{pct}% attack speed", (255, 230, 120)),
    "projectile_size": ("Amplify", 0.20, "+{pct}% projectile and area size", (200, 160, 255)),
    "extra_projectiles": ("Multicast", 1, "+{num} projectile for every element", (255, 180, 90)),
    "pickup_radius": ("Crystal Magnet", 0.20, "+{pct}% XP collection radius", (90, 200, 255)),
    "max_hp": ("Vitality", 25, "+{num} maximum health", (255, 90, 120)),
    "regen": ("Regeneration", 0.6, "Regenerate {dec} HP per second", (120, 255, 150)),
}


class StatUpgrade(Upgrade):
    def __init__(self, stat, rarity):
        super().__init__(f"stat:{stat}", rarity)
        self._stat = stat

    def _amount(self):
        base = STAT_INFO[self._stat][1]
        if self._stat == "extra_projectiles":
            return 2 if self._rarity.power >= 3 else 1
        if self._stat == "max_hp":
            return int(base * self._rarity.power)
        return base * self._rarity.power

    @property
    def color(self):
        return STAT_INFO[self._stat][3]

    @property
    def icon(self):
        return ("stat", self._stat)

    def title(self):
        return STAT_INFO[self._stat][0]

    def description(self):
        amount = self._amount()
        return STAT_INFO[self._stat][2].format(pct=int(round(amount * 100)), num=int(amount),
                                               dec=f"{amount:.1f}")

    def apply(self, player, world):
        player.improve_stat(self._stat, self._amount())


# --------------------------------------------------------------------------
# Element upgrades
# --------------------------------------------------------------------------
class NewElementUpgrade(Upgrade):
    category = "element"

    def __init__(self, element_id, rarity):
        super().__init__(f"new:{element_id}", rarity)
        self._element_id = element_id

    def _start_level(self):
        return (1, 1, 2, 3)[self._rarity.rank]

    @property
    def color(self):
        return ELEMENT_COLORS[self._element_id]

    @property
    def icon(self):
        return ("element", self._element_id)

    def title(self):
        return f"Awaken {element_display_name(self._element_id)}"

    def description(self):
        cls = ELEMENT_CLASSES[self._element_id]
        level = self._start_level()
        extra = f" Starts at level {level}." if level > 1 else ""
        return f"New element: {cls.attack_name}. {cls.effect_text}{extra}"

    def apply(self, player, world):
        player.add_element(self._element_id, self._start_level())
        world.check_fusion_hint()


class ElementLevelUpgrade(Upgrade):
    category = "element"

    def __init__(self, element_id, rarity):
        super().__init__(f"lvl:{element_id}", rarity)
        self._element_id = element_id

    def _levels(self):
        return (1, 1, 2, 3)[self._rarity.rank]

    @property
    def color(self):
        return ELEMENT_COLORS[self._element_id]

    @property
    def icon(self):
        return ("element", self._element_id)

    def title(self):
        return f"{element_display_name(self._element_id)} +{self._levels()}"

    def description(self):
        text = f"+{self._levels()} level: more damage, faster casts, more projectiles."
        if self._rarity.rank == 1:
            text += " Bonus: +10% damage."
        return text

    def apply(self, player, world):
        element = player.get_element(self._element_id)
        element.level_up(self._levels())
        if self._rarity.rank == 1:
            player.improve_stat("damage", 0.1)


class ElementSpecialUpgrade(Upgrade):
    """The unique upgrade of each element (Fire damage, Lightning chains...)."""
    category = "element"

    def __init__(self, element_id, rarity):
        super().__init__(f"special:{element_id}", rarity)
        self._element_id = element_id

    @property
    def color(self):
        return ELEMENT_COLORS[self._element_id]

    @property
    def icon(self):
        return ("element", self._element_id)

    def title(self):
        cls = ELEMENT_CLASSES[self._element_id]
        return f"{cls.name}: {cls.special_title}"

    def description(self):
        cls = ELEMENT_CLASSES[self._element_id]
        return cls().special_text(self._rarity.power).capitalize() + "."

    def apply(self, player, world):
        player.get_element(self._element_id).improve_special(self._rarity.power)


# --------------------------------------------------------------------------
# Fusion upgrades
# --------------------------------------------------------------------------
class FusionUnlockUpgrade(Upgrade):
    category = "fusion"

    def __init__(self, recipe, rarity):
        super().__init__(f"fuse:{recipe.fusion_id}", rarity)
        self._recipe = recipe

    @property
    def color(self):
        return self._recipe.color

    @property
    def icon(self):
        return ("fusion", self._recipe.fusion_id)

    def title(self):
        return f"FUSION: {self._recipe.name}"

    def description(self):
        bonus = "" if self._rarity.rank == 0 else f" Starts empowered (+{int(30 * (self._rarity.power - 1))}% dmg)."
        return self._recipe.description + bonus

    def apply(self, player, world):
        fusion = player.add_fusion(self._recipe)
        if self._rarity.rank > 0:
            fusion.upgrade("damage", self._rarity.power - 1)
        world.register_fusion(self._recipe)


FUSION_STAT_TEXT = {
    "damage": ("Power", "+{pct}% damage"),
    "cooldown": ("Haste", "-{pct}% cooldown"),
    "area": ("Expanse", "+{pct}% area of effect"),
    "count": ("Echo", "+{num} {label}"),
}


class FusionStatUpgrade(Upgrade):
    category = "fusion"

    def __init__(self, fusion, stat, rarity):
        super().__init__(f"fus:{fusion.fusion_id}:{stat}", rarity)
        self._fusion_id = fusion.fusion_id
        self._name = fusion.name
        self._color = fusion.color
        self._label = fusion.count_label
        self._stat = stat

    @property
    def color(self):
        return self._color

    @property
    def icon(self):
        return ("fusion", self._fusion_id)

    def title(self):
        return f"{self._name}: {FUSION_STAT_TEXT[self._stat][0]}"

    def description(self):
        power = self._rarity.power
        pct = {"damage": 30 * power, "cooldown": min(50, 10 * power), "area": 15 * power}.get(self._stat, 0)
        num = 2 if power >= 3 else 1
        return FUSION_STAT_TEXT[self._stat][1].format(pct=int(pct), num=num, label=self._label) + "."

    def apply(self, player, world):
        player.get_fusion(self._fusion_id).upgrade(self._stat, self._rarity.power)


class HealUpgrade(Upgrade):
    """Fallback when nothing else is available."""

    def __init__(self, rarity):
        super().__init__("heal", rarity)

    @property
    def color(self):
        return (255, 90, 120)

    @property
    def icon(self):
        return ("stat", "max_hp")

    def title(self):
        return "Second Wind"

    def description(self):
        return f"Restore {int(min(100, 35 * self._rarity.power))}% of your health."

    def apply(self, player, world):
        player.heal(player.stats.max_hp * min(1.0, 0.35 * self._rarity.power))


# --------------------------------------------------------------------------
# The pool
# --------------------------------------------------------------------------
class UpgradePool:
    """Builds the list of valid upgrades for the current player and rolls choices."""

    def __init__(self, rng):
        self._rng = rng

    def roll_rarity(self, min_rank=0):
        options = [r for r in RARITIES if r.rank >= min_rank]
        total = sum(r.weight for r in options)
        roll = self._rng.random() * total
        for rarity in options:
            roll -= rarity.weight
            if roll <= 0:
                return rarity
        return options[-1]

    def candidates(self, player):
        """List of (weight, factory) for every upgrade that is valid right now.

        A factory is a function rarity -> Upgrade. Invalid upgrades (maxed
        elements, fusions you don't own, ...) are never added.
        """
        options = []
        for stat in STAT_INFO:
            if player.stats.can_improve(stat):
                weight = 4 if stat == "extra_projectiles" else 9
                options.append((weight, lambda r, s=stat: StatUpgrade(s, r)))

        owned = [e for e in ELEMENT_IDS if player.has_element(e)]
        new_weight = 16 if len(owned) <= 2 else 9
        for element_id in ELEMENT_IDS:
            element = player.get_element(element_id)
            if element is None:
                options.append((new_weight, lambda r, e=element_id: NewElementUpgrade(e, r)))
            else:
                if not element.is_max_level:
                    options.append((13, lambda r, e=element_id: ElementLevelUpgrade(e, r)))
                options.append((5, lambda r, e=element_id: ElementSpecialUpgrade(e, r)))

        for recipe in eligible_recipes(player):
            options.append((32, lambda r, rec=recipe: FusionUnlockUpgrade(rec, r)))

        for fusion in player.fusions:
            if fusion.is_max_level:
                continue
            stats = ["damage", "cooldown", "area"] + (["count"] if fusion.supports_count else [])
            for stat in stats:
                options.append((6, lambda r, f=fusion, s=stat: FusionStatUpgrade(f, s, r)))
        return options

    def roll(self, player, count=3, min_rank=0):
        """Pick `count` different upgrades, weighted, each with a random rarity."""
        options = self.candidates(player)
        chosen = []
        used_ids = set()
        while options and len(chosen) < count:
            total = sum(w for w, _ in options)
            roll = self._rng.random() * total
            index = len(options) - 1
            for i, (weight, _) in enumerate(options):
                roll -= weight
                if roll <= 0:
                    index = i
                    break
            _, factory = options.pop(index)
            upgrade = factory(self.roll_rarity(min_rank))
            if upgrade.upgrade_id not in used_ids:
                used_ids.add(upgrade.upgrade_id)
                chosen.append(upgrade)
        while len(chosen) < count:
            chosen.append(HealUpgrade(self.roll_rarity(min_rank)))
        return chosen
