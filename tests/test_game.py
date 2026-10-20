"""Tests for creating game objects without running the game loop."""

import os
import unittest
from unittest.mock import patch

# Use SDL's dummy drivers so tests need neither a window nor audio hardware.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from main import Game
from src.arena import ArenaLayout, create_fixed_arena


class GameSetupTests(unittest.TestCase):
    def tearDown(self):
        pygame.quit()

    def test_constructor_does_not_start_game_loop(self):
        with patch.object(Game, "run") as run:
            game = Game()

        run.assert_not_called()
        self.assertEqual(len(game.players), 2)

    def test_default_round_uses_fixed_layout(self):
        game = Game()
        arena = create_fixed_arena()

        self.assertEqual([obstacle.rect for obstacle in game.obstacles], arena.obstacles)
        self.assertEqual(game.player1.rect.center, arena.player1_spawn)
        self.assertEqual(game.player2.rect.center, arena.player2_spawn)
        self.assertEqual(list(game.all_sprites), [*game.obstacles, *game.players])

    def test_multiple_obstacles_are_created_from_layout(self):
        game = Game()
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
        self.assertEqual(list(game.all_sprites), [*game.obstacles, *game.players])


if __name__ == "__main__":
    unittest.main()
