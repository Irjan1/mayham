"""Check PNG previews without opening a game window."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pygame

from config import DESTRUCTIBLE_COLOR, HEIGHT, OBSTACLE_COLOR, WIDTH
from src.arena import generate_arena
from tools.preview_arenas import main, save_previews


class ArenaPreviewTests(unittest.TestCase):
    def tearDown(self):
        pygame.quit()

    def test_seed_command_writes_image_with_matching_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'seed42.png'
            with patch('sys.argv', ['preview_arenas', '--seed', '42', '--output', str(output)]):
                main()
            image = pygame.image.load(str(output))
            self.assertEqual(image.get_size(), (WIDTH + 24, HEIGHT + 88))
            arena = generate_arena(42)
            for rect in arena.obstacles:
                color = DESTRUCTIBLE_COLOR if rect in arena.destructible_obstacles else OBSTACLE_COLOR
                self.assertEqual(tuple(image.get_at((12 + rect.centerx, 48 + rect.centery)))[:3], color)
            for hazard in arena.hazards:
                self.assertNotEqual(tuple(image.get_at((12 + hazard.centerx, 48 + hazard.centery)))[:3],
                                    (0, 0, 0))
            self.assertIsNone(pygame.display.get_surface())

    def test_multiple_seeds_produce_grid_png(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'grid.png'
            with patch('sys.argv', ['preview_arenas', '--start', '0', '--count', '4',
                                    '--output', str(output)]):
                main()
            image = pygame.image.load(str(output))
            self.assertGreater(image.get_width(), WIDTH // 2)
            self.assertGreater(image.get_height(), HEIGHT // 2)
            self.assertIsNone(pygame.display.get_surface())

    def test_style_option_renders_each_style(self):
        for style in ("open", "corridors", "scattered"):
            with self.subTest(style=style), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / f'{style}.png'
                with patch('sys.argv', ['preview_arenas', '--seed', '42', '--style', style,
                                        '--output', str(output)]):
                    main()
                self.assertTrue(output.is_file())
                self.assertEqual(pygame.image.load(str(output)).get_width(), WIDTH + 24)

    def test_empty_seed_list_is_rejected(self):
        with self.assertRaises(ValueError):
            save_previews([], Path('unused.png'))


if __name__ == "__main__":
    unittest.main()
