"""Upgrade selection, persistence and arena rotation through the existing Game."""

from collections import defaultdict
import os
import random
import unittest
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame

from config import BULLET_COOLDOWN, FUEL_COLOR, FUEL_SIZE, GRAVITY, THRUST
from main import Game
from src.arena import ARENA_STYLES, generate_arena
from src.game_events import GameEvents
from src.objects import Bullet, Fuel
from src.upgrades import UPGRADES, apply_upgrade, create_upgrade_levels


class UpgradeRoundTests(unittest.TestCase):
    def setUp(self):
        self.saved_scores = GameEvents.player_scores.copy()
        GameEvents.player_scores.update(Player1=0, Player2=0)

    def tearDown(self):
        GameEvents.player_scores.clear()
        GameEvents.player_scores.update(self.saved_scores)
        pygame.quit()

    def finish_round(self, game, loser):
        winner = game.player2 if loser is game.player1 else game.player1
        loser.needs.health = 0
        game.game_events.player_died(loser, winner)
        due = game.game_events.get_game_winner_time() + game.winner_show_delay + game.winner_choose_delay
        with patch('pygame.time.get_ticks', return_value=due):
            game.update_game()
        return due

    def choose_card(self, game, upgrade_id):
        index = game.upgrade_choices.index(upgrade_id)
        now = game.game_events.get_game_winner_time() + game.winner_show_delay + game.winner_choose_delay + 1
        with patch('pygame.time.get_ticks', return_value=now):
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=(pygame.K_1, pygame.K_2, pygame.K_3)[index]))
            game.handle_events()
            game.draw()
        with patch('pygame.time.get_ticks', return_value=now + game.upgrade_confirmation_delay):
            game.update_game()

    def test_first_round_has_no_upgrades_or_selection(self):
        game = Game(seed=42)
        self.assertIsNone(game.upgrade_player)
        self.assertEqual(game.upgrade_choices, [])
        for levels in game.upgrade_levels.values():
            self.assertEqual(levels, create_upgrade_levels())
        for player in game.players:
            self.assertEqual(player.needs.health, 100)
            self.assertEqual(player.needs.max_health, 100)
            self.assertEqual(player.bullet_cooldown, BULLET_COOLDOWN)
            self.assertEqual(player.thrust, THRUST)

    def test_only_losing_player_gets_an_offer(self):
        for loser_name in ('Player1', 'Player2'):
            with self.subTest(loser=loser_name):
                game = Game(seed=42, fixed_arena=True)
                loser = game.player1 if loser_name == 'Player1' else game.player2
                self.finish_round(game, loser)
                self.assertEqual(game.upgrade_player, loser_name)
                self.assertEqual(set(game.upgrade_choices), set(UPGRADES))
                self.assertEqual(game.arena_seed, 42)
                self.assertTrue(all(level == 0 for levels in game.upgrade_levels.values()
                                    for level in levels.values()))

    def test_selection_freezes_movement_bullets_fuel_and_gameplay_timestamps(self):
        game = Game(seed=42, fixed_arena=True)
        bullet = Bullet(500, 100, 0, game.player1)
        fuel = Fuel(300, 100, FUEL_SIZE, FUEL_COLOR)
        game.bullets.add(bullet)
        game.fuel_cans.add(fuel)
        game.all_sprites.add(bullet, fuel)
        game.time_from_fuel_spawn = -100000
        self.finish_round(game, game.player2)
        player = game.player1
        player_state = (player.x, player.y, player.vx, player.vy, player.needs.health,
                        player.needs.fuel, player.last_fuel, player.last_shot, player.last_wall_damage)
        bullet_position = (bullet.x, bullet.y)
        winner_time = game.game_events.get_game_winner_time()
        fuel_state = game.fuel_rng.getstate()
        offer_state = game.upgrade_rng.getstate()
        choices = game.upgrade_choices.copy()
        for _ in range(5):
            game.update_game()
            game.handle_winner_time(winner_time)
        self.assertEqual(player_state, (player.x, player.y, player.vx, player.vy, player.needs.health,
                                      player.needs.fuel, player.last_fuel, player.last_shot,
                                      player.last_wall_damage))
        self.assertEqual((bullet.x, bullet.y), bullet_position)
        self.assertIn(fuel, game.fuel_cans)
        fuel.kill()
        game.spawn_fuel()
        self.assertEqual(len(game.fuel_cans), 0)
        self.assertEqual(game.time_from_fuel_spawn, -100000)
        self.assertEqual(game.game_events.get_game_winner_time(), winner_time)
        self.assertEqual(game.fuel_rng.getstate(), fuel_state)
        self.assertEqual(game.upgrade_rng.getstate(), offer_state)
        self.assertEqual(game.upgrade_choices, choices)
        self.assertEqual(game.arena_seed, 42)

    def test_number_keys_apply_one_card_and_transition_exactly_once(self):
        game = Game(seed=42, fixed_arena=True)
        due = self.finish_round(game, game.player2)
        winner_time = game.game_events.get_game_winner_time()
        chosen = game.upgrade_choices[0]
        pygame.event.clear()
        with patch('pygame.time.get_ticks', return_value=due + 1):
            for key in (pygame.K_1, pygame.K_2, pygame.K_1):
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
            game.handle_events()
        self.assertEqual(game.selected_upgrade_index, 0)
        self.assertEqual(game.upgrade_levels['Player2'][chosen], 1)
        self.assertEqual(sum(game.upgrade_levels['Player2'].values()), 1)
        self.assertEqual(game.upgrade_levels['Player1'], create_upgrade_levels())
        self.assertEqual(game.arena_seed, 42)
        game.draw()
        with patch('pygame.time.get_ticks', return_value=due + game.upgrade_confirmation_delay):
            game.update_game()
        self.assertEqual(game.arena_seed, 42)
        with patch('pygame.time.get_ticks', return_value=due + 1 + game.upgrade_confirmation_delay):
            game.update_game()
            game.update_game()
            game.handle_winner_time(winner_time)
        self.assertEqual(game.arena_seed, 43)
        self.assertIsNone(game.upgrade_player)
        self.assertEqual(sum(game.upgrade_levels['Player2'].values()), 1)
        self.assertEqual(GameEvents.get_scores(), {'Player1': 1, 'Player2': 0})

    def test_upgrades_persist_when_upgraded_player_wins_later(self):
        game = Game(seed=42, fixed_arena=True)
        self.finish_round(game, game.player2)
        self.choose_card(game, 'reinforced_hull')
        self.assertEqual(game.player2.needs.health, 120)
        self.assertEqual(game.player1.needs.health, 100)
        self.finish_round(game, game.player1)
        self.choose_card(game, 'rapid_fire')
        self.assertEqual(game.player2.needs.max_health, 120)
        self.assertEqual(game.player2.needs.health, 120)
        self.assertEqual(game.player1.bullet_cooldown, 255)
        self.assertEqual(game.player2.bullet_cooldown, 300)
        self.assertEqual(game.upgrade_levels['Player2']['reinforced_hull'], 1)
        self.assertEqual(game.upgrade_levels['Player1']['reinforced_hull'], 0)
        self.assertEqual(GameEvents.get_scores(), {'Player1': 1, 'Player2': 1})

    def test_maxed_card_is_excluded_and_remaining_keys_are_validated(self):
        game = Game(seed=42, fixed_arena=True)
        game.upgrade_levels['Player2']['reinforced_hull'] = 2
        self.finish_round(game, game.player2)
        self.assertEqual(set(game.upgrade_choices), {'rapid_fire', 'enhanced_thrusters'})
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3))
        game.handle_events()
        self.assertIsNone(game.selected_upgrade_index)
        self.assertEqual(game.arena_seed, 42)
        game.draw()

    def test_all_maxed_loser_skips_selection(self):
        game = Game(seed=42, fixed_arena=True)
        game.upgrade_levels['Player2'] = {upgrade_id: 2 for upgrade_id in UPGRADES}
        self.finish_round(game, game.player2)
        self.assertEqual(game.arena_seed, 43)
        self.assertIsNone(game.upgrade_player)
        self.assertEqual(game.upgrade_choices, [])
        self.assertEqual(game.player2.needs.health, 140)
        self.assertEqual(game.player2.bullet_cooldown, 210)
        self.assertAlmostEqual(game.player2.thrust, 0.13)

    def test_draw_at_timestamp_zero_skips_selection_and_cannot_be_overwritten(self):
        game = Game(seed=42, fixed_arena=True)
        offer_state = game.upgrade_rng.getstate()
        with patch('pygame.time.get_ticks', return_value=0):
            game.game_events.game_winner(None)
            game.game_events.game_winner(game.player1)
        self.assertIsNone(game.game_events.get_game_winner())
        self.assertEqual(GameEvents.get_scores(), {'Player1': 0, 'Player2': 0})
        with patch('pygame.time.get_ticks', return_value=game.winner_show_delay):
            game.draw()
        with patch('pygame.time.get_ticks', return_value=game.winner_show_delay + game.winner_choose_delay):
            game.update_game()
            game.handle_winner_time(0)
        self.assertEqual(game.arena_seed, 43)
        self.assertIsNone(game.upgrade_player)
        self.assertEqual(game.upgrade_rng.getstate(), offer_state)

    def test_new_game_session_resets_upgrade_levels(self):
        first = Game(seed=42, fixed_arena=True)
        apply_upgrade(first.upgrade_levels['Player1'], 'reinforced_hull')
        first.start_new_round()
        self.assertEqual(first.player1.needs.health, 120)
        second = Game(seed=42, fixed_arena=True)
        self.assertEqual(second.upgrade_levels['Player1'], create_upgrade_levels())
        self.assertEqual(second.upgrade_levels['Player2'], create_upgrade_levels())
        self.assertEqual(second.player1.needs.health, 100)
        self.assertEqual(first.upgrade_levels['Player1']['reinforced_hull'], 1)

    def test_player_stats_do_not_compound_or_change_unrelated_movement_values(self):
        game = Game(seed=42, fixed_arena=True)
        levels = {upgrade_id: 2 for upgrade_id in UPGRADES}
        player = game.player1
        player.needs.fuel = 73
        rotation = player.rotation_speed
        fuel_cooldown = player.fuel_cooldown
        for _ in range(3):
            player.apply_upgrades(levels)
            self.assertEqual(player.needs.max_health, 140)
            self.assertEqual(player.needs.health, 140)
            self.assertEqual(player.bullet_cooldown, 210)
            self.assertAlmostEqual(player.thrust, 0.13)
            self.assertEqual(player.gravity, GRAVITY)
            self.assertEqual(player.rotation_speed, rotation)
            self.assertEqual(player.needs.fuel, 73)
            self.assertEqual(player.fuel_cooldown, fuel_cooldown)

    def test_selected_max_level_card_keeps_the_offered_level_on_screen(self):
        game = Game(seed=42, fixed_arena=True)
        game.upgrade_levels['Player2']['reinforced_hull'] = 1
        self.finish_round(game, game.player2)
        game.select_upgrade(game.upgrade_choices.index('reinforced_hull'))
        self.assertEqual(game.upgrade_levels['Player2']['reinforced_hull'], 2)
        self.assertEqual(game.upgrade_screen.levels['reinforced_hull'], 1)
        game.draw()

    def test_rapid_fire_uses_the_upgraded_cooldown_when_shooting(self):
        game = Game(seed=42, fixed_arena=True)
        levels = create_upgrade_levels()
        levels['rapid_fire'] = 2
        game.player1.apply_upgrades(levels)
        with patch('pygame.time.get_ticks', return_value=1000):
            game.player1.shoot(game.bullets)
        with patch('pygame.time.get_ticks', return_value=1209):
            game.player1.shoot(game.bullets)
        self.assertEqual(len(game.bullets), 1)
        with patch('pygame.time.get_ticks', return_value=1210):
            game.player1.shoot(game.bullets)
        self.assertEqual(len(game.bullets), 2)

    def test_enhanced_thrusters_accelerate_without_extra_fuel_consumption(self):
        game = Game(seed=42, fixed_arena=True)
        levels = create_upgrade_levels()
        levels['enhanced_thrusters'] = 2
        game.player1.apply_upgrades(levels)
        keys = defaultdict(bool)
        keys[game.player1.controls['up']] = True
        with patch('pygame.time.get_ticks', return_value=1000):
            game.player1.handle_input(keys, game.bullets)
            self.assertAlmostEqual(game.player1.vy, -THRUST * 1.3)
            self.assertEqual(game.player1.needs.fuel, 99)
            game.player1.handle_input(keys, game.bullets)
            self.assertEqual(game.player1.needs.fuel, 99)


class ArenaRotationTests(unittest.TestCase):
    def tearDown(self):
        pygame.quit()

    def test_each_bag_contains_all_styles_and_boundaries_do_not_repeat(self):
        game = Game(seed=42)
        styles = [game.arena.style]
        for _ in range(11):
            game.start_new_round()
            styles.append(game.arena.style)
        for index in range(0, 12, 3):
            self.assertEqual(set(styles[index:index + 3]), set(ARENA_STYLES))
        for index in range(1, 12):
            self.assertNotEqual(styles[index - 1], styles[index])
        self.assertEqual(game.arena_seed, 53)

    def test_starting_seed_repeats_layouts_independent_of_other_random_streams(self):
        state = random.getstate()
        first = Game(seed=42)
        expected = [first.arena]
        for _ in range(8):
            first.start_new_round()
            expected.append(first.arena)
        second = Game(seed=42)
        actual = [second.arena]
        for _ in range(8):
            for _ in range(20):
                second.fuel_rng.random()
                second.upgrade_rng.random()
            second.start_new_round()
            actual.append(second.arena)
        self.assertEqual(actual, expected)
        self.assertEqual(random.getstate(), state)
        for seed, arena in enumerate(actual, start=42):
            self.assertEqual(arena, generate_arena(seed, arena.style))

    def test_explicit_style_and_fixed_room_bypass_bag(self):
        for style in ARENA_STYLES:
            game = Game(seed=42, style=style)
            for _ in range(4):
                self.assertEqual(game.arena.style, style)
                game.start_new_round()
            self.assertEqual(game.style_bag, [])
        game = Game(seed=42, fixed_arena=True)
        game.start_new_round()
        self.assertEqual(game.arena.style, 'fixed')
        self.assertEqual(game.style_bag, [])


if __name__ == '__main__':
    unittest.main()
