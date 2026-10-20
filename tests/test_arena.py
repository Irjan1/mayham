"""Tests for the original arena geometry."""

import unittest

import pygame

from src.arena import create_fixed_arena


class FixedArenaTests(unittest.TestCase):
    def test_obstacle_position_and_size(self):
        arena = create_fixed_arena()

        self.assertEqual(arena.obstacles, [pygame.Rect(460, 280, 160, 160)])

    def test_player_spawn_positions(self):
        arena = create_fixed_arena()

        self.assertEqual(arena.player1_spawn, (270, 180))
        self.assertEqual(arena.player2_spawn, (810, 540))

    def test_layouts_do_not_share_mutable_obstacles(self):
        first_arena = create_fixed_arena()
        second_arena = create_fixed_arena()

        first_arena.obstacles[0].move_ip(10, 20)
        first_arena.obstacles.clear()

        self.assertEqual(second_arena.obstacles, [pygame.Rect(460, 280, 160, 160)])


if __name__ == "__main__":
    unittest.main()
