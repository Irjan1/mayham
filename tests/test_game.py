"""Round integration and existing gameplay checks without an interactive loop."""

from collections import defaultdict
from contextlib import redirect_stdout
import io
import os
import random
import unittest
from unittest.mock import patch

# Use SDL's dummy drivers so tests need neither a window nor audio hardware.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from config import BULLET_DAMAGE, FUEL_COLOR, FUEL_SIZE, STARTING_FUEL, STARTING_HEALTH, WALL_DAMAGE
from main import Game
from src.arena import ArenaLayout, create_fixed_arena, generate_arena, validate_arena
from src.game_events import GameEvents
from src.objects import Bullet, Fuel


class GameSetupTests(unittest.TestCase):
    def setUp(self):
        self.saved_scores = GameEvents.player_scores.copy()
        GameEvents.player_scores.update(Player1=0, Player2=0)

    def tearDown(self):
        GameEvents.player_scores.clear()
        GameEvents.player_scores.update(self.saved_scores)
        pygame.quit()

    def test_constructor_does_not_start_game_loop(self):
        with patch.object(Game, "run") as run:
            game = Game(seed=42)

        run.assert_not_called()
        self.assertEqual(len(game.players), 2)

    def test_first_round_uses_valid_generated_layout_and_prints_seed(self):
        output = io.StringIO()
        with redirect_stdout(output):
            game = Game(seed=42)

        self.assertEqual(game.arena_seed, 42)
        self.assertEqual(game.arena, generate_arena(42, game.arena.style))
        self.assertTrue(validate_arena(game.arena))
        self.assertIn("Arena seed: 42", output.getvalue())
        self.assertEqual([obstacle.rect for obstacle in game.obstacles], game.arena.obstacles)
        self.assertEqual(game.player1.rect.center, game.arena.player1_spawn)
        self.assertEqual(game.player2.rect.center, game.arena.player2_spawn)
        self.assertEqual(list(game.all_sprites), [*game.obstacles, *game.hazards, *game.players])

    def test_fixed_arena_debug_option_preserves_original_room(self):
        game = Game(seed=42, fixed_arena=True)
        arena = create_fixed_arena()

        self.assertEqual(game.arena, arena)
        self.assertEqual([obstacle.rect for obstacle in game.obstacles], arena.obstacles)
        self.assertEqual(game.player1.rect.center, arena.player1_spawn)
        self.assertEqual(game.player2.rect.center, arena.player2_spawn)

    def test_next_round_increments_seed_and_changes_layout(self):
        game = Game(seed=42)
        first_arena = game.arena

        game.start_new_round()

        self.assertEqual(game.arena_seed, 43)
        self.assertEqual(game.arena, generate_arena(43, game.arena.style))
        self.assertNotEqual(game.arena, first_arena)
        self.assertTrue(validate_arena(game.arena))
        self.assertEqual([obstacle.rect for obstacle in game.obstacles], game.arena.obstacles)
        self.assertEqual(game.player1.rect.center, game.arena.player1_spawn)
        self.assertEqual(game.player2.rect.center, game.arena.player2_spawn)
        self.assertEqual(list(game.all_sprites), [*game.obstacles, *game.hazards, *game.players])

    def test_multiple_obstacles_are_created_from_layout(self):
        game = Game(seed=42)
        arena = ArenaLayout(
            obstacles=[pygame.Rect(100, 200, 80, 60), pygame.Rect(600, 300, 120, 90)],
            player1_spawn=(90, 120),
            player2_spawn=(900, 600),
        )

        game.game_objects(arena)

        self.assertEqual([obstacle.rect for obstacle in game.obstacles], arena.obstacles)
        self.assertEqual([obstacle.image.get_size() for obstacle in game.obstacles],
                         [(80, 60), (120, 90)])
        self.assertEqual(game.player1.rect.center, arena.player1_spawn)
        self.assertEqual(game.player2.rect.center, arena.player2_spawn)
        self.assertEqual(list(game.all_sprites), [*game.obstacles, *game.hazards, *game.players])

    def test_new_round_removes_all_old_sprites(self):
        game = Game(seed=42)
        bullet = Bullet(game.player1.x, game.player1.y, 0, game.player1)
        fuel = Fuel(100, 100, FUEL_SIZE, FUEL_COLOR)
        # Also cover a bullet created before it reaches the drawing group.
        game.bullets.add(bullet)
        game.fuel_cans.add(fuel)
        game.all_sprites.add(fuel)
        old_sprites = [*game.players, *game.obstacles, *game.hazards, bullet, fuel]
        old_drawing_group = game.all_sprites

        game.start_new_round()

        self.assertEqual(len(game.bullets), 0)
        self.assertEqual(len(game.fuel_cans), 0)
        self.assertEqual(len(old_drawing_group), 0)
        for sprite in old_sprites:
            self.assertEqual(sprite.groups(), [])
            self.assertNotIn(sprite, game.all_sprites)

    def test_scores_persist_and_player_needs_reset_after_winner_delay(self):
        game = Game(seed=42)
        game.player1.needs.fuel = 10
        game.player1.needs.health = 20
        game.game_events.player_died(game.player2, game.player1)
        winner_time = game.game_events.get_game_winner_time()
        round_delay = game.winner_show_delay + game.winner_choose_delay

        with patch('pygame.time.get_ticks', return_value=winner_time + round_delay - 1):
            game.handle_winner_time(winner_time)
        self.assertEqual(game.arena_seed, 42)
        with patch('pygame.time.get_ticks', return_value=winner_time + round_delay):
            game.handle_winner_time(winner_time)
            self.assertEqual(game.upgrade_player, "Player2")
            game.select_upgrade(game.upgrade_choices.index('rapid_fire'))
        next_round_time = winner_time + round_delay + game.upgrade_confirmation_delay
        with patch('pygame.time.get_ticks', return_value=next_round_time):
            game.update_game()

        self.assertEqual(game.arena_seed, 43)
        self.assertEqual(GameEvents.get_scores(), {"Player1": 1, "Player2": 0})
        self.assertIsNone(game.game_events.get_game_winner())
        self.assertIsNone(game.game_events.get_game_winner_time())
        self.assertEqual(game.time_from_fuel_spawn, next_round_time)
        for player in game.players:
            self.assertEqual(player.needs.health, STARTING_HEALTH)
            self.assertEqual(player.needs.fuel, STARTING_FUEL)
            self.assertTrue(player.is_alive)
        game.draw()

    def test_fuel_randomness_does_not_change_later_arena_or_global_state(self):
        state = random.getstate()
        game = Game(seed=42)
        for _ in range(10):
            game.fuel_rng.random()
        game.start_new_round()

        self.assertEqual(game.arena, generate_arena(43, game.arena.style))
        self.assertEqual(random.getstate(), state)

    def test_starting_seed_zero_reproduces_same_layout(self):
        first = Game(seed=0)
        second = Game(seed=0)

        self.assertEqual(first.arena_seed, 0)
        self.assertEqual(first.arena, second.arena)
        self.assertEqual(first.fuel_positions, second.fuel_positions)

    def test_unseeded_start_does_not_modify_global_random_state(self):
        state = random.getstate()
        game = Game()

        self.assertIsInstance(game.arena_seed, int)
        self.assertEqual(random.getstate(), state)

    def test_fuel_timing_and_collection_are_preserved(self):
        game = Game(seed=42)
        original_time = game.time_from_fuel_spawn
        due_time = original_time + game.fuel_spawn_time + 1
        with patch('pygame.time.get_ticks', return_value=due_time - 1):
            game.spawn_fuel()
        self.assertEqual(len(game.fuel_cans), 0)
        with patch('pygame.time.get_ticks', return_value=due_time):
            game.spawn_fuel()
            game.spawn_fuel()

        self.assertEqual(len(game.fuel_cans), 1)
        self.assertEqual(game.time_from_fuel_spawn, due_time)
        fuel = next(iter(game.fuel_cans))
        self.assertIn(fuel, game.all_sprites)
        game.player1.x, game.player1.y = fuel.rect.center
        game.player1.update_rect()
        game.player1.needs.fuel = 10
        game.player1.pick_up_fuel(game.fuel_cans)

        self.assertEqual(game.player1.needs.fuel, 10 + STARTING_FUEL // 2)
        self.assertEqual(fuel.groups(), [])

    def test_no_fuel_position_skips_spawn_and_allows_later_retry(self):
        game = Game(seed=42)
        positions = game.fuel_positions
        game.fuel_positions = []
        due_time = game.time_from_fuel_spawn + game.fuel_spawn_time + 1
        with patch('pygame.time.get_ticks', return_value=due_time):
            game.spawn_fuel()
            self.assertEqual(len(game.fuel_cans), 0)
            self.assertNotEqual(game.time_from_fuel_spawn, due_time)
            game.fuel_positions = positions
            game.spawn_fuel()
        self.assertEqual(len(game.fuel_cans), 1)

    def test_both_players_can_thrust_and_shoot(self):
        game = Game(seed=42)
        with patch('pygame.time.get_ticks', return_value=1000):
            for player in game.players:
                keys = defaultdict(bool)
                keys[player.controls['up']] = True
                keys[player.controls['shoot']] = True
                old_position = (player.x, player.y)
                # Movement uses the previous frame's velocity, so run two frames.
                for _ in range(2):
                    player.update(keys, game.obstacles, game.players, game.bullets,
                                  game.fuel_cans, game.game_events)
                self.assertNotEqual((player.x, player.y), old_position)
                self.assertLess(player.vy, 0)
                self.assertEqual(player.needs.fuel, STARTING_FUEL - 1)
        self.assertEqual(len(game.bullets), 2)
        self.assertEqual({bullet.owner for bullet in game.bullets}, set(game.players))

    def test_bullets_damage_both_players(self):
        game = Game(seed=42)
        for owner, target in ((game.player1, game.player2), (game.player2, game.player1)):
            bullet = Bullet(target.x, target.y, 0, owner)
            bullet.vx = bullet.vy = 0
            game.bullets.add(bullet)
            bullet.update(game.players, game.obstacles, game.game_events)
            self.assertEqual(target.needs.health, STARTING_HEALTH - BULLET_DAMAGE)
            self.assertEqual(bullet.groups(), [])

    def test_players_collide_with_different_generated_obstacles(self):
        game = Game(seed=42)
        keys = defaultdict(bool)
        with patch('pygame.time.get_ticks', return_value=1000):
            for player, obstacle in zip(game.players, game.obstacles):
                player.x = obstacle.rect.centerx
                player.y = obstacle.rect.top - player.radius - 1
                old_position = (player.x, player.y)
                player.vx, player.vy = 0, 2
                player.update_rect()
                player.update(keys, game.obstacles, game.players, game.bullets,
                              game.fuel_cans, game.game_events)
                self.assertEqual((player.x, player.y), old_position)
                self.assertEqual(player.needs.health, STARTING_HEALTH - WALL_DAMAGE)


if __name__ == "__main__":
    unittest.main()
