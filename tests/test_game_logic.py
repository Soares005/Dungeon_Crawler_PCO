"""Automated tests for the game logic (no window needed).

Run from the project folder with:
    python -m unittest discover tests
"""
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pygame.math import Vector2  # noqa: E402

from settings import ELEMENT_IDS, MAX_ELEMENT_LEVEL  # noqa: E402
from status import Burning, Slowed, Wet, StatusSet  # noqa: E402
from enemies import BasicEnemy, BossEnemy, TankEnemy  # noqa: E402
from world import World  # noqa: E402
from fusions import FUSION_RECIPES, FUSIONS_BY_ID  # noqa: E402
from upgrades import UpgradePool, FusionUnlockUpgrade, FusionStatUpgrade, ElementLevelUpgrade  # noqa: E402
from save_manager import SaveManager, RunRecord, clean_name  # noqa: E402


def make_world(element="fire"):
    return World(element, seed=1)


def place_enemy(world, cls=BasicEnemy, offset=(60, 0), hp_mult=1.0):
    enemy = cls(world.player.pos + Vector2(offset), hp_mult)
    world.add_enemy(enemy)
    world.update(0.0, (0, 0))          # flush the spawn queue and rebuild the grid
    return enemy


class StatusTests(unittest.TestCase):
    def test_burning_deals_damage_over_time(self):
        statuses = StatusSet()
        statuses.apply(Burning(2.0, dps=10))
        damage = statuses.update(1.0)
        self.assertAlmostEqual(damage["fire"], 10.0)

    def test_refresh_keeps_strongest_slow(self):
        statuses = StatusSet()
        statuses.apply(Slowed(1.0, 0.5))
        statuses.apply(Slowed(3.0, 0.2))
        self.assertAlmostEqual(statuses.speed_multiplier(), 0.5)

    def test_statuses_expire(self):
        statuses = StatusSet()
        statuses.apply(Wet(0.5))
        statuses.update(1.0)
        self.assertFalse(statuses.has("wet"))


class EnemyTests(unittest.TestCase):
    def test_damage_kills(self):
        enemy = BasicEnemy((0, 0))
        enemy.take_damage(enemy.max_hp + 1)
        self.assertFalse(enemy.alive)
        self.assertEqual(enemy.hp, 0)

    def test_chill_stacks_freeze(self):
        enemy = TankEnemy((0, 0))
        froze = [enemy.add_chill(1, 0.4, 2.0) for _ in range(3)]
        self.assertEqual(froze, [False, False, True])
        self.assertTrue(enemy.has_status("frozen"))

    def test_boss_cannot_be_frozen(self):
        boss = BossEnemy((0, 0), 0)
        for _ in range(3):
            boss.add_chill(1, 0.4, 2.0)
        self.assertFalse(boss.has_status("frozen"))
        self.assertTrue(boss.has_status("slowed"))


class ReactionTests(unittest.TestCase):
    def test_wet_plus_lightning_conducts(self):
        world = make_world("lightning")
        target = place_enemy(world, hp_mult=50)
        neighbour = place_enemy(world, offset=(100, 0), hp_mult=50)
        target.apply_status(Wet(5))
        world.damage_enemy(target, 5, "lightning")
        self.assertFalse(target.has_status("wet"), "Conduction consumes Wet")
        self.assertLess(neighbour.hp, neighbour.max_hp, "the arc must reach the neighbour")
        self.assertIn(("reaction", "conduction"), world.drain_discoveries())

    def test_frozen_plus_earth_shatters_for_bonus_damage(self):
        world = make_world("earth")
        enemy = place_enemy(world, hp_mult=100)
        for _ in range(3):
            enemy.add_chill(1, 0.4, 2.0)
        dealt = world.damage_enemy(enemy, 10, "earth")
        self.assertGreater(dealt, 20)
        self.assertFalse(enemy.has_status("frozen"))

    def test_reaction_damage_does_not_recurse(self):
        world = make_world("lightning")
        for i in range(10):
            place_enemy(world, offset=(40 + i * 25, 0), hp_mult=50).apply_status(Wet(5))
        world.damage_enemy(world.enemies[0], 5, "lightning")   # must terminate


class FusionTests(unittest.TestCase):
    def test_ten_unique_recipes(self):
        self.assertEqual(len(FUSION_RECIPES), 10)
        pairs = {recipe.elements for recipe in FUSION_RECIPES}
        self.assertEqual(len(pairs), 10)
        for recipe in FUSION_RECIPES:
            self.assertEqual(len(recipe.elements), 2)
            self.assertTrue(recipe.elements <= set(ELEMENT_IDS))

    def test_eligibility_needs_both_elements_at_level_two(self):
        world = make_world("fire")
        player = world.player
        recipe = FUSIONS_BY_ID["fire_tornado"]
        self.assertFalse(recipe.is_eligible(player))
        player.add_element("wind", 2)
        self.assertFalse(recipe.is_eligible(player), "fire is still level 1")
        player.get_element("fire").level_up()
        self.assertTrue(recipe.is_eligible(player))
        player.add_fusion(recipe)
        self.assertFalse(recipe.is_eligible(player), "already unlocked")

    def test_every_fusion_activates(self):
        for recipe in FUSION_RECIPES:
            world = make_world()
            for i in range(12):
                place_enemy(world, offset=(80 + i * 15, (i % 3) * 30), hp_mult=20)
            fusion = recipe.create()
            self.assertTrue(fusion.activate(world, world.player), recipe.name)
            for _ in range(120):                # let the zones play out for 2 seconds
                world.update(1 / 60, (0, 0))
            self.assertGreater(world.summary()["kills"] + sum(1 for e in world.enemies if e.hp < e.max_hp), 0,
                               f"{recipe.name} should hurt something")


class UpgradeTests(unittest.TestCase):
    def test_choices_are_unique_and_valid(self):
        world = make_world()
        pool = UpgradePool(random.Random(5))
        for _ in range(200):
            choices = pool.roll(world.player, 3)
            ids = [c.upgrade_id for c in choices]
            self.assertEqual(len(ids), len(set(ids)))
            for choice in choices:
                if isinstance(choice, FusionStatUpgrade):
                    self.fail("no fusion owned, fusion upgrades must not be offered")
                if isinstance(choice, FusionUnlockUpgrade):
                    self.fail("no fusion is eligible yet")

    def test_maxed_element_not_offered(self):
        world = make_world()
        world.player.get_element("fire").level_up(MAX_ELEMENT_LEVEL)
        pool = UpgradePool(random.Random(1))
        for _ in range(200):
            for choice in pool.roll(world.player, 3):
                self.assertFalse(isinstance(choice, ElementLevelUpgrade) and "fire" in choice.upgrade_id)

    def test_reward_rolls_are_epic_or_better(self):
        world = make_world()
        pool = UpgradePool(random.Random(2))
        for _ in range(50):
            for choice in pool.roll(world.player, 3, min_rank=2):
                self.assertGreaterEqual(choice.rarity.rank, 2)

    def test_applying_every_offer_works(self):
        world = make_world()
        pool = UpgradePool(random.Random(9))
        for _ in range(60):
            choice = pool.roll(world.player, 3)[0]
            choice.apply(world.player, world)
        self.assertGreaterEqual(len(world.player.elements), 1)


class SaveTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._dir.name, "save_data.json")

    def tearDown(self):
        self._dir.cleanup()

    def test_round_trip(self):
        save = SaveManager(self.path)
        save.discover("fusion", "blizzard")
        save.discover("reaction", "shatter")
        save.add_record(RunRecord("Ana", 321.5, 900, 18, ["blizzard"]))
        save.settings.change_volume(-0.3)
        self.assertTrue(save.save())
        loaded = SaveManager(self.path)
        self.assertTrue(loaded.load())
        self.assertEqual(loaded.discovered_fusions, {"blizzard"})
        self.assertEqual(loaded.discovered_reactions, {"shatter"})
        self.assertEqual(loaded.records[0].name, "Ana")
        self.assertAlmostEqual(loaded.settings.volume, 0.3)

    def test_corrupted_file_does_not_crash(self):
        with open(self.path, "w", encoding="utf-8") as file:
            file.write("{ this is not json")
        save = SaveManager(self.path)
        self.assertFalse(save.load())
        self.assertTrue(save.last_error)
        self.assertEqual(save.records, [])

    def test_bad_values_are_ignored(self):
        data = {"codex": {"fusions": ["blizzard", "not_a_fusion", 42]},
                "records": [{"name": "Ok", "time": 10, "kills": 1, "level": 1}, {"name": "Broken"}, "junk"],
                "settings": {"volume": "loud", "screen_shake": "yes"}}
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(data, file)
        save = SaveManager(self.path)
        save.load()
        self.assertEqual(save.discovered_fusions, {"blizzard"})
        self.assertEqual(len(save.records), 1)
        self.assertEqual(save.settings.volume, 0.6)
        self.assertTrue(save.settings.screen_shake)

    def test_clean_name(self):
        self.assertEqual(clean_name("  <Ana>!!  "), "Ana")
        self.assertEqual(clean_name(""), "Player")
        self.assertEqual(len(clean_name("x" * 50)), 12)


class SimulationTest(unittest.TestCase):
    def test_two_minutes_of_play(self):
        """Smoke test: a full run with random upgrades must not raise."""
        world = make_world("water")
        pool = UpgradePool(random.Random(3))
        t = 0.0
        while world.time < 120 and not world.game_over:
            t += 1 / 30
            world.update(1 / 30, (Vector2(1, 0).rotate(t * 40)))
            world.events.drain()
            while world.pending_level_ups or world.pending_rewards:
                pool.roll(world.player, 3)[0].apply(world.player, world)
                if world.pending_rewards:
                    world.consume_reward()
                else:
                    world.consume_level_up()
        self.assertGreater(world.kills, 0)


if __name__ == "__main__":
    unittest.main()
