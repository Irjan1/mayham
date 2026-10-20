"""Geometry tests for finite, reachable fuel placement."""

import random
import unittest
from unittest.mock import patch

import pygame

from config import FUEL_SIZE, HEIGHT, PLAYER_RADIUS, WIDTH
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


if __name__ == "__main__":
    unittest.main()
