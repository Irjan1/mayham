"""Pure upgrade rules: levels, eligibility and base-stat calculations."""

import random
import unittest
from unittest.mock import patch

from config import BULLET_COOLDOWN, BULLET_DAMAGE, BULLET_RADIUS, STARTING_HEALTH, THRUST
from src.upgrades import (
    UPGRADES, apply_upgrade, choose_upgrade_offers, create_upgrade_levels, effective_stats,
)


class UpgradeRulesTests(unittest.TestCase):
    def test_fresh_levels_are_zero_and_independent(self):
        first = create_upgrade_levels()
        second = create_upgrade_levels()
        self.assertTrue(all(level == 0 for level in first.values()))
        apply_upgrade(first, 'reinforced_hull')
        self.assertEqual(second['reinforced_hull'], 0)

    def test_base_and_level_one_and_two_stats(self):
        levels = create_upgrade_levels()
        self.assertEqual(effective_stats(levels), {
            'max_health': STARTING_HEALTH, 'bullet_cooldown': BULLET_COOLDOWN, 'thrust': THRUST,
            'bullet_radius': BULLET_RADIUS, 'bullet_damage': BULLET_DAMAGE,
            'bullet_bounces': 0, 'explosion_radius': 0,
        })
        for level, expected_health, expected_cooldown, expected_thrust in (
            (1, 120, 255, 0.115), (2, 140, 210, 0.13),
        ):
            with self.subTest(level=level):
                levels = {upgrade_id: level for upgrade_id in UPGRADES}
                stats = effective_stats(levels)
                self.assertEqual(stats['max_health'], expected_health)
                self.assertEqual(stats['bullet_cooldown'], expected_cooldown)
                self.assertAlmostEqual(stats['thrust'], expected_thrust)
                self.assertEqual(stats['bullet_radius'], 4 + level)
                self.assertEqual(stats['bullet_damage'], 20 + 4 * level)
                self.assertEqual(stats['bullet_bounces'], level)
                self.assertEqual(stats['explosion_radius'], (0, 48, 72)[level])

    def test_each_upgrade_changes_only_its_own_stat(self):
        base = effective_stats(create_upgrade_levels())
        for upgrade_id, changed_stat in (
            ('reinforced_hull', 'max_health'), ('rapid_fire', 'bullet_cooldown'),
            ('enhanced_thrusters', 'thrust'),
            ('larger_bullets', 'bullet_radius'), ('heavy_bullets', 'bullet_damage'),
            ('ricochet', 'bullet_bounces'), ('explosive_rounds', 'explosion_radius'),
        ):
            with self.subTest(upgrade=upgrade_id):
                levels = create_upgrade_levels()
                apply_upgrade(levels, upgrade_id)
                stats = effective_stats(levels)
                self.assertNotEqual(stats[changed_stat], base[changed_stat])
                for name in base:
                    if name != changed_stat:
                        self.assertEqual(stats[name], base[name])

    def test_levels_are_capped_and_unknown_upgrades_are_ignored(self):
        levels = create_upgrade_levels()
        for upgrade_id in UPGRADES:
            self.assertTrue(apply_upgrade(levels, upgrade_id))
            self.assertTrue(apply_upgrade(levels, upgrade_id))
            self.assertFalse(apply_upgrade(levels, upgrade_id))
            self.assertEqual(levels[upgrade_id], 2)
        self.assertFalse(apply_upgrade(levels, 'unknown'))
        self.assertNotIn('unknown', levels)

    def test_offers_are_unique_and_exclude_maxed_upgrades(self):
        levels = create_upgrade_levels()
        rng = random.Random(42)
        choices = choose_upgrade_offers(levels, rng)
        self.assertEqual(len(UPGRADES), 7)
        self.assertEqual(len(choices), 3)
        self.assertTrue(set(choices).issubset(UPGRADES))
        self.assertEqual(len(choices), len(set(choices)))
        levels['reinforced_hull'] = 2
        choices = choose_upgrade_offers(levels, rng)
        self.assertNotIn('reinforced_hull', choices)
        levels = {upgrade_id: 2 for upgrade_id in UPGRADES}
        levels['ricochet'] = 1
        self.assertEqual(choose_upgrade_offers(levels, rng), ['ricochet'])
        levels['ricochet'] = 2
        self.assertEqual(choose_upgrade_offers(levels, rng), [])

    def test_offers_support_sampling_from_a_larger_pool(self):
        extra = {'name': 'Future upgrade', 'effects': ('Level one', 'Level two'), 'max_level': 2}
        with patch.dict(UPGRADES, {'future_upgrade': extra}):
            levels = create_upgrade_levels()
            seen = set()
            for seed in range(20):
                choices = choose_upgrade_offers(levels, random.Random(seed))
                self.assertEqual(len(choices), 3)
                self.assertEqual(len(set(choices)), 3)
                seen.update(choices)
            self.assertEqual(seen, set(UPGRADES))

    def test_offers_are_seeded_without_changing_global_random_state(self):
        levels = create_upgrade_levels()
        state = random.getstate()
        self.assertEqual(choose_upgrade_offers(levels, random.Random(42)),
                         choose_upgrade_offers(levels, random.Random(42)))
        self.assertEqual(random.getstate(), state)


if __name__ == '__main__':
    unittest.main()
