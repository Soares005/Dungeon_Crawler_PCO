"""Elemental Reactions: automatic interactions between a hit and the statuses
already on the target (e.g. Lightning hitting a Wet enemy).

Each reaction is a subclass of Reaction that overrides trigger(). The
ReactionSystem holds the list of reactions (data-driven: add a subclass to
the list and it works everywhere, for basic attacks and fusions alike).
"""
from abc import ABC, abstractmethod

from settings import ELEMENT_COLORS, FIRE, WATER, LIGHTNING, ICE, EARTH, WIND
from status import Burning, Frozen, Electrified
from zones import SteamCloud


class Reaction(ABC):
    reaction_id = "reaction"
    name = "Reaction"
    status = ""              # status the target must have
    trigger_element = ""     # element of the incoming hit
    consumes = True          # does the reaction remove the status?
    cooldown = 0.3           # per enemy
    description = ""
    color = (255, 255, 255)

    def matches(self, enemy, element):
        return element == self.trigger_element and enemy.has_status(self.status)

    @abstractmethod
    def trigger(self, world, enemy, damage):
        """Do the reaction. Return a damage multiplier for the triggering hit."""


class Conduction(Reaction):
    reaction_id = "conduction"
    name = "Conduction"
    status, trigger_element = "wet", LIGHTNING
    description = "Lightning hits a Wet enemy: electricity arcs to up to 5 nearby enemies."
    color = (120, 220, 255)

    def trigger(self, world, enemy, damage):
        world.chain_lightning(enemy.pos, None, damage * 0.6, 5, 170, origin_enemy=enemy,
                              on_hit=lambda e: e.apply_status(Electrified(2.0, damage * 0.05)),
                              color=self.color, allow_reactions=False, prefer_status="wet")
        return 1.3


class Wildfire(Reaction):
    reaction_id = "wildfire"
    name = "Wildfire"
    status, trigger_element = "burning", WIND
    consumes = False
    cooldown = 0.6
    description = "Wind hits a Burning enemy: the flames spread to everything nearby."
    color = (255, 150, 60)

    def trigger(self, world, enemy, damage):
        spread = world.enemies_in_radius(enemy.pos, 120)
        for other in spread:
            if other is not enemy:
                other.apply_status(Burning(3.0, max(3.0, damage * 0.6)))
        world.events.push("wildfire", enemy.pos, color=self.color, value=120)
        return 1.25


class Shatter(Reaction):
    reaction_id = "shatter"
    name = "Shatter"
    status, trigger_element = "frozen", EARTH
    description = "Earth hits a Frozen enemy: it shatters for huge damage and an icy explosion."
    color = (200, 240, 255)

    def trigger(self, world, enemy, damage):
        world.explode(enemy.pos, 100, damage * 0.8, ICE, exclude=enemy, shake=5,
                      color=self.color, allow_reactions=False)
        return 2.5


class FlashFreeze(Reaction):
    reaction_id = "flash_freeze"
    name = "Flash Freeze"
    status, trigger_element = "wet", ICE
    description = "Ice hits a Wet enemy: it freezes solid instantly."
    color = ELEMENT_COLORS[ICE]

    def trigger(self, world, enemy, damage):
        enemy.apply_status(Frozen(1.8))
        world.events.push("freeze", enemy.pos, color=self.color)
        return 1.2


class SteamBurst(Reaction):
    reaction_id = "steam_burst"
    name = "Steam Burst"
    status, trigger_element = "burning", WATER
    description = "Water hits a Burning enemy: a scalding steam cloud bursts out."
    color = (230, 235, 245)

    def trigger(self, world, enemy, damage):
        world.spawn_effect(SteamCloud(enemy.pos, 75, 2.5, max(2.0, damage * 0.35)))
        return 1.0


class Overload(Reaction):
    reaction_id = "overload"
    name = "Overload"
    status, trigger_element = "burning", LIGHTNING
    description = "Lightning hits a Burning enemy: it overloads in a fiery explosion."
    color = (255, 190, 80)

    def trigger(self, world, enemy, damage):
        world.explode(enemy.pos, 80, damage * 0.9, FIRE, shake=3, color=self.color,
                      allow_reactions=False)
        return 1.0


class Melt(Reaction):
    reaction_id = "melt"
    name = "Melt"
    status, trigger_element = "frozen", FIRE
    description = "Fire hits a Frozen enemy: the ice melts violently for double damage."
    color = (255, 170, 120)

    def trigger(self, world, enemy, damage):
        world.events.push("explosion", enemy.pos, color=self.color, value=40)
        return 2.0


ALL_REACTIONS = (Conduction(), Wildfire(), Shatter(), FlashFreeze(), SteamBurst(), Overload(), Melt())
REACTIONS_BY_ID = {r.reaction_id: r for r in ALL_REACTIONS}


class ReactionSystem:
    def __init__(self, reactions=ALL_REACTIONS):
        self._reactions = list(reactions)

    def process(self, world, enemy, element, damage):
        """Check every reaction for this hit. Returns the total damage multiplier."""
        multiplier = 1.0
        for reaction in self._reactions:
            if reaction.matches(enemy, element) and enemy.reaction_ready(
                    reaction.reaction_id, world.time, reaction.cooldown):
                if reaction.consumes:
                    enemy.consume_status(reaction.status)
                multiplier *= reaction.trigger(world, enemy, damage)
                world.register_reaction(reaction, enemy)
        return multiplier
