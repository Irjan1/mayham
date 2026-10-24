"""Geometry tests for finite, reachable fuel placement."""

import os
import random
import unittest
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame

from config import (
    FUEL_RESPAWN_DELAY, FUEL_WARNING_DURATION, FUEL_SIZE, HEIGHT, PLAYER_RADIUS,
    STARTING_FUEL, WIDTH,
)
from main import Game
from src.arena import (
    FUEL_PLAYER_CLEARANCE, GRID_SIZE, ArenaLayout, choose_fuel_position,
    create_fixed_arena, generate_arena, get_fuel_positions, get_reachable_cells,
    rectangle_fits,
)
from src.geometry import circle_intersects_rect


class FuelPlacementTests(unittest.TestCase):
    def test_candidates_fit_and_belong_to_navigable_region(self):
        for seed in range(20):
            with self.subTest(seed=seed):
                arena = generate_arena(seed)
                positions = get_fuel_positions(arena)
                reachable = get_reachable_cells(arena)
                self.assertTrue(positions)
                for position in positions:
                    rect = pygame.Rect(position, FUEL_SIZE)
                    self.assertTrue(rectangle_fits(rect, arena.obstacles + arena.hazards))
                    self.assertIn((rect.centerx // GRID_SIZE, rect.centery // GRID_SIZE), reachable)

    def test_full_rectangle_is_checked_even_if_larger_than_grid_cell(self):
        arena = create_fixed_arena()
        normal_positions = get_fuel_positions(arena)
        with patch('src.arena.FUEL_SIZE', (120, 120)):
            larger_positions = get_fuel_positions(arena)
        self.assertTrue(larger_positions)
        self.assertLess(len(larger_positions), len(normal_positions))
        for position in larger_positions:
            self.assertTrue(rectangle_fits(pygame.Rect(position, (120, 120)), arena.obstacles))

    def test_disconnected_region_has_no_candidates(self):
        arena = ArenaLayout(
            obstacles=[pygame.Rect(WIDTH // 2, 0, 20, HEIGHT)],
            player1_spawn=(120, 360),
            player2_spawn=(960, 360),
        )
        positions = get_fuel_positions(arena)

        self.assertTrue(positions)
        self.assertTrue(all(x < WIDTH // 2 for x, y in positions))

    def test_destroyed_obstacles_open_new_safe_fuel_positions(self):
        wall = pygame.Rect(WIDTH // 2, 0, 20, HEIGHT)
        hazard = pygame.Rect(750, 300, 100, 32)
        arena = ArenaLayout([wall], (120, 360), (960, 360), hazards=[hazard],
                            destructible_obstacles=[wall])
        before = get_fuel_positions(arena)
        after = get_fuel_positions(arena, obstacles=[])
        self.assertTrue(all(x < WIDTH // 2 for x, y in before))
        self.assertTrue(any(x > WIDTH // 2 for x, y in after))
        self.assertTrue(all(rectangle_fits(pygame.Rect(position, FUEL_SIZE), [hazard])
                            for position in after))
        self.assertEqual(arena.obstacles, [wall])

    def test_selection_avoids_current_player_positions(self):
        arena = generate_arena(42)
        positions = get_fuel_positions(arena)
        # Move players to candidate positions, rather than using original spawns.
        occupied_rects = [pygame.Rect(position, FUEL_SIZE) for position in positions[:2]]
        player_positions = [rect.center for rect in occupied_rects]
        rng = random.Random(42)
        for _ in range(30):
            position = choose_fuel_position(positions, player_positions, rng)
            self.assertIsNotNone(position)
            rect = pygame.Rect(position, FUEL_SIZE)
            for player in player_positions:
                self.assertFalse(circle_intersects_rect(
                    player, PLAYER_RADIUS + FUEL_PLAYER_CLEARANCE, rect,
                ))

    def test_empty_or_fully_occupied_candidates_return_none(self):
        rng = random.Random(42)
        self.assertIsNone(choose_fuel_position([], [], rng))
        positions = [(100, 100), (800, 500)]
        players = [pygame.Rect(position, FUEL_SIZE).center for position in positions]
        self.assertIsNone(choose_fuel_position(positions, players, rng))

    def test_selection_is_reproducible_and_does_not_change_global_random_state(self):
        positions = get_fuel_positions(generate_arena(42))
        state = random.getstate()
        first_rng = random.Random(42)
        second_rng = random.Random(42)
        first = [choose_fuel_position(positions, [], first_rng) for _ in range(10)]
        second = [choose_fuel_position(positions, [], second_rng) for _ in range(10)]

        self.assertEqual(first, second)
        self.assertEqual(random.getstate(), state)


class FuelLifecycleTests(unittest.TestCase):
    def setUp(self):
        with patch('pygame.time.get_ticks', return_value=1000):
            self.game = Game(seed=42, fixed_arena=True)
        self.initial_deadline = self.game.fuel_spawn_at

    def tearDown(self):
        pygame.quit()

    def announce(self):
        self.game.update_fuel(self.game.fuel_spawn_at - FUEL_WARNING_DURATION)
        self.assertEqual(self.game.fuel_state, 'warning')
        return self.game.fuel_spawn_position

    def spawn(self):
        position = self.announce()
        self.game.update_fuel(self.game.fuel_spawn_at)
        fuel = next(iter(self.game.fuel_cans))
        self.assertEqual(fuel.rect.topleft, position)
        return fuel

    def collect(self, fuel, now):
        self.game.player1.x, self.game.player1.y = fuel.rect.center
        self.game.player1.update_rect()
        self.game.player1.needs.fuel = 10
        # Exercise collection and lifecycle detection through the normal frame update.
        with patch('pygame.time.get_ticks', return_value=now):
            self.game.update_game()
        self.assertEqual(self.game.player1.needs.fuel, 10 + STARTING_FUEL // 2)
        self.assertEqual(len(self.game.fuel_cans), 0)
        self.assertEqual(self.game.fuel_state, 'waiting')
        self.assertEqual(self.game.fuel_spawn_at, now + FUEL_RESPAWN_DELAY)

    def test_initial_delay_and_exact_warning_and_spawn_boundaries(self):
        self.assertEqual(self.initial_deadline, 1000 + FUEL_RESPAWN_DELAY)
        warning_at = self.initial_deadline - FUEL_WARNING_DURATION
        state = self.game.fuel_rng.getstate()
        self.game.update_fuel(warning_at - 1)
        self.assertEqual(self.game.fuel_state, 'waiting')
        self.assertIsNone(self.game.fuel_spawn_position)
        self.assertEqual(self.game.fuel_rng.getstate(), state)
        position = self.announce()
        self.assertIn(position, self.game.fuel_positions)
        self.game.update_fuel(self.initial_deadline - 1)
        self.assertEqual(len(self.game.fuel_cans), 0)
        self.game.update_fuel(self.initial_deadline)
        self.assertEqual(self.game.fuel_state, 'active')
        self.assertEqual(next(iter(self.game.fuel_cans)).rect.topleft, position)
        self.assertIsNone(self.game.fuel_spawn_at)
        self.assertIsNone(self.game.fuel_spawn_position)

    def test_active_can_has_no_deadline_and_late_collection_starts_full_delay(self):
        fuel = self.spawn()
        state = self.game.fuel_rng.getstate()
        for now in (20000, 60000, 300000):
            self.game.update_fuel(now)
            self.assertEqual(list(self.game.fuel_cans), [fuel])
            self.assertIsNone(self.game.fuel_spawn_at)
            self.assertEqual(self.game.fuel_state, 'active')
        self.assertEqual(self.game.fuel_rng.getstate(), state)
        self.collect(fuel, 300001)
        self.game.update_fuel(300002)
        self.assertEqual(len(self.game.fuel_cans), 0)
        self.assertIsNone(self.game.fuel_spawn_position)

    def test_immediate_collection_and_multiple_complete_cycles(self):
        now = self.initial_deadline
        for _ in range(3):
            fuel = self.spawn()
            self.collect(fuel, now)
            self.game.update_fuel(now + 1)
            self.assertEqual(len(self.game.fuel_cans), 0)
            now += FUEL_RESPAWN_DELAY

    def test_warning_is_not_collectible_and_guards_do_not_move_reservation(self):
        position = self.announce()
        self.game.player1.x, self.game.player1.y = pygame.Rect(position, FUEL_SIZE).center
        self.game.player1.update_rect()
        self.game.player1.needs.fuel = 10
        self.game.player1.pick_up_fuel(self.game.fuel_cans)
        self.assertEqual(self.game.player1.needs.fuel, 10)
        self.assertEqual(len(self.game.fuel_cans), 0)
        self.assertNotIn(self.game.fuel_warning_image, self.game.all_sprites)
        state = self.game.fuel_rng.getstate()
        for now in (4500, 7000, 10999):
            self.game.update_fuel(now)
            self.assertEqual(self.game.fuel_spawn_position, position)
        self.game.update_fuel(self.initial_deadline)
        self.assertEqual(next(iter(self.game.fuel_cans)).rect.topleft, position)
        self.assertEqual(self.game.fuel_rng.getstate(), state)

    def test_warning_pulses_without_changing_game_state_or_randomness(self):
        self.announce()
        image = self.game.fuel_warning_image
        state = (self.game.fuel_state, self.game.fuel_spawn_at,
                 self.game.fuel_spawn_position, self.game.fuel_rng.getstate(), random.getstate())
        with patch('pygame.time.get_ticks', return_value=4250):
            self.game.draw()
        bright = pygame.image.tobytes(self.game.screen, 'RGB')
        with patch('pygame.time.get_ticks', return_value=4750):
            self.game.draw()
        dim = pygame.image.tobytes(self.game.screen, 'RGB')
        self.assertNotEqual(bright, dim)
        self.assertIs(self.game.fuel_warning_image, image)
        self.assertEqual((self.game.fuel_state, self.game.fuel_spawn_at,
                          self.game.fuel_spawn_position, self.game.fuel_rng.getstate(), random.getstate()), state)

    def test_new_round_and_arena_replacement_clear_reservations_and_active_fuel(self):
        self.announce()
        with patch('pygame.time.get_ticks', return_value=50000):
            self.game.start_new_round()
        self.assertEqual(self.game.arena_seed, 43)
        self.assertEqual(self.game.fuel_state, 'waiting')
        self.assertIsNone(self.game.fuel_spawn_position)
        self.assertEqual(self.game.fuel_spawn_at, 50000 + FUEL_RESPAWN_DELAY)
        fuel = self.spawn()
        with patch('pygame.time.get_ticks', return_value=80000):
            self.game.game_objects(create_fixed_arena())
        self.assertEqual(fuel.groups(), [])
        self.assertEqual(len(self.game.fuel_cans), 0)
        self.assertEqual(self.game.fuel_state, 'waiting')
        self.assertIsNone(self.game.fuel_spawn_position)
        self.assertEqual(self.game.fuel_spawn_at, 80000 + FUEL_RESPAWN_DELAY)

    def test_no_safe_site_retries_and_gives_full_warning_when_a_site_opens(self):
        positions = self.game.fuel_positions
        self.game.fuel_positions = []
        self.game.update_fuel(4000)
        self.game.update_fuel(20000)
        self.assertEqual(self.game.fuel_state, 'waiting')
        self.assertIsNone(self.game.fuel_spawn_position)
        self.game.fuel_positions = positions
        self.game.update_fuel(20000)
        self.assertEqual(self.game.fuel_state, 'warning')
        self.assertEqual(self.game.fuel_spawn_at, 20000 + FUEL_WARNING_DURATION)
        self.game.update_fuel(20000 + FUEL_WARNING_DURATION - 1)
        self.assertEqual(len(self.game.fuel_cans), 0)
        self.game.update_fuel(20000 + FUEL_WARNING_DURATION)
        self.assertEqual(len(self.game.fuel_cans), 1)

    def test_warning_duration_is_clamped_and_can_be_disabled(self):
        with patch('main.FUEL_WARNING_DURATION', FUEL_RESPAWN_DELAY * 2):
            self.game.update_fuel(1000)
            self.assertEqual(self.game.fuel_state, 'warning')
            self.assertEqual(self.game.fuel_spawn_at, self.initial_deadline)
        self.game.game_objects(create_fixed_arena())
        deadline = self.game.fuel_spawn_at
        with patch('main.FUEL_WARNING_DURATION', 0):
            self.game.update_fuel(deadline - 1)
            self.assertEqual(self.game.fuel_state, 'waiting')
            self.game.update_fuel(deadline)
            self.assertEqual(self.game.fuel_state, 'active')
            self.assertEqual(len(self.game.fuel_cans), 1)

    def test_seeded_reservations_repeat_without_changing_arenas_or_global_rng(self):
        first = self.announce()
        state = random.getstate()
        with patch('pygame.time.get_ticks', return_value=1000):
            other = Game(seed=42, fixed_arena=True)
        other.update_fuel(4000)
        self.assertEqual(other.fuel_spawn_position, first)
        self.assertEqual(other.fuel_rng.getstate(), self.game.fuel_rng.getstate())
        self.assertEqual(other.arena, self.game.arena)
        other.start_new_round()
        self.game.start_new_round()
        self.assertEqual(other.arena, self.game.arena)
        self.assertEqual(random.getstate(), state)

    def test_updates_do_not_create_duplicate_cans(self):
        fuel = self.spawn()
        for _ in range(10):
            self.game.update_fuel(100000)
        self.assertEqual(list(self.game.fuel_cans), [fuel])
        self.assertEqual(sum(sprite is fuel for sprite in self.game.all_sprites), 1)


if __name__ == "__main__":
    unittest.main()
