"""Deterministic scenery, preview output and the small round integration."""

from collections import Counter
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame

from config import HEIGHT, WIDTH
from main import Game
from src import background
from src.gui import UpgradeSelection


class BackgroundTests(unittest.TestCase):
    def test_style_configuration_is_consistent(self):
        styles = set(background.STYLE_WEIGHTS)
        self.assertEqual(styles, {'empty', 'planet', 'galaxy', 'nebula', 'black_hole', 'nova'})
        self.assertEqual(styles, set(background.STYLE_DRAWERS))
        self.assertEqual(styles, set(background.STAR_DENSITY))
        self.assertTrue(all(weight >= 0 for weight in background.STYLE_WEIGHTS.values()))
        self.assertGreater(sum(background.STYLE_WEIGHTS.values()), 0)
        self.assertTrue(all(density >= 0 for density in background.STAR_DENSITY.values()))
        for value in (background.BRIGHTNESS, background.OPACITY, background.RING_CHANCE,
                      background.GALAXY_SPIRAL_CHANCE, background.CLUSTER_CHANCE):
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 1)
        palettes = [*background.BASE_PALETTES]
        palettes += [background.PLANET_COLORS, background.GALAXY_COLORS,
                     background.NEBULA_COLORS, background.BLACK_HOLE_COLORS,
                     background.NOVA_COLORS, background.STAR_COLORS]
        for palette in palettes:
            for color in palette:
                self.assertEqual(len(color), 3)
                self.assertTrue(all(0 <= channel <= 255 for channel in color))

    def test_same_seed_size_and_style_produce_identical_pixels(self):
        for style in [None, *background.STYLE_WEIGHTS]:
            with self.subTest(style=style):
                first, first_style = background.generate_background(42, (320, 200), style)
                second, second_style = background.generate_background(42, (320, 200), style)
                self.assertEqual(first_style, second_style)
                self.assertEqual(first.get_alpha(), second.get_alpha())
                self.assertEqual(pygame.image.tobytes(first, 'RGB'),
                                 pygame.image.tobytes(second, 'RGB'))

    def test_forcing_selected_style_reproduces_automatic_composition(self):
        automatic, style = background.generate_background(42, (320, 200))
        forced, _ = background.generate_background(42, (320, 200), style)
        self.assertEqual(pygame.image.tobytes(automatic, 'RGB'),
                         pygame.image.tobytes(forced, 'RGB'))

    def test_different_seeds_vary_each_style(self):
        for style in background.STYLE_WEIGHTS:
            with self.subTest(style=style):
                first, _ = background.generate_background(1, (320, 200), style)
                second, _ = background.generate_background(2, (320, 200), style)
                self.assertNotEqual(pygame.image.tobytes(first, 'RGB'),
                                    pygame.image.tobytes(second, 'RGB'))

    def test_weighted_selection_includes_all_styles_and_keeps_rare_styles_rare(self):
        rng = random.Random(42)
        counts = Counter(background.choose_style(rng) for _ in range(2000))
        self.assertEqual(set(counts), set(background.STYLE_WEIGHTS))
        for style, weight in background.STYLE_WEIGHTS.items():
            # Wide tolerance verifies weighting without testing an exact random sequence.
            self.assertAlmostEqual(counts[style] / 2000, weight / 100, delta=0.04)
        with patch.object(background, 'STYLE_WEIGHTS', {'empty': 0, 'planet': 1}):
            self.assertEqual(background.choose_style(random.Random(0)), 'planet')

    def test_invalid_weights_sizes_styles_and_fades_are_rejected(self):
        for weights in ({}, {'empty': 0}, {'empty': -1, 'planet': 2}):
            with patch.object(background, 'STYLE_WEIGHTS', weights):
                with self.assertRaises(ValueError):
                    background.choose_style(random.Random(0))
        for size in ((0, 100), (100, -1)):
            with self.assertRaises(ValueError):
                background.generate_background(42, size)
        with self.assertRaises(ValueError):
            background.generate_background(42, (100, 100), 'unknown')
        for setting in ('BRIGHTNESS', 'OPACITY'):
            with patch.object(background, setting, 1.1):
                with self.assertRaises(ValueError):
                    background.generate_background(42, (100, 100))

    def test_all_styles_render_at_current_and_small_viewports_without_display(self):
        pygame.display.quit()
        for style in background.STYLE_WEIGHTS:
            for size in ((WIDTH, HEIGHT), (64, 48), (1, 1)):
                with self.subTest(style=style, size=size):
                    surface, selected = background.generate_background(42, size, style)
                    self.assertEqual(surface.get_size(), size)
                    self.assertEqual(selected, style)
                    self.assertIsNone(pygame.display.get_surface())

    def test_global_fade_controls_apply_to_every_style(self):
        for style in background.STYLE_WEIGHTS:
            with self.subTest(style=style):
                with patch.object(background, 'BRIGHTNESS', 0):
                    surface, _ = background.generate_background(42, (100, 80), style)
                self.assertEqual(pygame.image.tobytes(surface, 'RGB'), bytes(100 * 80 * 3))
                with patch.object(background, 'OPACITY', 0.25):
                    surface, _ = background.generate_background(42, (100, 80), style)
                self.assertEqual(surface.get_alpha(), round(255 * 0.25))

    def test_generation_does_not_consume_global_random_state(self):
        state = random.getstate()
        for style in background.STYLE_WEIGHTS:
            background.generate_background(42, (320, 200), style)
        self.assertEqual(random.getstate(), state)

    def test_preview_cli_saves_grid_and_single_forced_style_without_display(self):
        pygame.display.quit()
        with tempfile.TemporaryDirectory() as directory:
            for arguments in (['--start', '10', '--count', '6'],
                              ['--seed', '42', '--style', 'black_hole']):
                output = Path(directory) / 'preview.png'
                with patch('sys.argv', ['background', *arguments, '--width', '320',
                                        '--height', '200', '--output', str(output)]):
                    background.main()
                image = pygame.image.load(str(output))
                self.assertGreater(image.get_height(), 200)
                self.assertGreater(image.get_width(), 320)
                self.assertIsNone(pygame.display.get_surface())
        pygame.font.quit()


class BackgroundIntegrationTests(unittest.TestCase):
    def tearDown(self):
        pygame.quit()

    def test_background_is_cached_until_next_round_in_both_arena_modes(self):
        for fixed in (False, True):
            with self.subTest(fixed=fixed):
                with patch('main.generate_background', wraps=background.generate_background) as generate:
                    game = Game(seed=42, fixed_arena=fixed)
                    cached = game.background
                    pixels = pygame.image.tobytes(cached, 'RGB')
                    for _ in range(3):
                        game.update_game()
                        game.draw()
                    generate.assert_called_once_with(42, (WIDTH, HEIGHT))
                    self.assertIs(game.background, cached)
                    self.assertEqual(pygame.image.tobytes(cached, 'RGB'), pixels)
                    game.start_new_round()
                    self.assertEqual(generate.call_count, 2)
                    generate.assert_called_with(43, (WIDTH, HEIGHT))
                    self.assertIsNot(game.background, cached)

    def test_background_does_not_change_arena_fuel_upgrade_or_effects_randomness(self):
        blank = pygame.Surface((WIDTH, HEIGHT))
        with patch('main.generate_background', return_value=(blank, 'empty')):
            baseline = Game(seed=42)
            expected = []
            for _ in range(3):
                expected.append((baseline.arena, baseline.fuel_positions,
                                 baseline.style_rng.getstate(), baseline.fuel_rng.getstate(),
                                 baseline.upgrade_rng.getstate(), baseline.effects.rng.getstate()))
                baseline.start_new_round()
        actual = Game(seed=42)
        for snapshot in expected:
            self.assertEqual((actual.arena, actual.fuel_positions,
                              actual.style_rng.getstate(), actual.fuel_rng.getstate(),
                              actual.upgrade_rng.getstate(), actual.effects.rng.getstate()), snapshot)
            actual.start_new_round()

    def test_background_stays_behind_sprites_and_preserves_black_upgrade_screen(self):
        game = Game(seed=42, fixed_arena=True)
        game.background.fill((10, 20, 30))
        game.background.set_alpha(255)
        obstacle = next(iter(game.obstacles))
        point = obstacle.rect.center
        game.effects.add(point, (0, 0), (255, 255, 255), 5, 0.2)
        game.draw()
        self.assertEqual(game.screen.get_at((0, HEIGHT - 1))[:3], (10, 20, 30))
        self.assertEqual(game.screen.get_at(point), obstacle.image.get_at(
            (obstacle.rect.width // 2, obstacle.rect.height // 2)))

        game.upgrade_player = 'Player1'
        game.upgrade_screen = UpgradeSelection('Player1', ['rapid_fire'], game.upgrade_levels['Player1'])
        game.draw()
        self.assertEqual(game.screen.get_at((0, HEIGHT - 1))[:3], (0, 0, 0))


if __name__ == '__main__':
    unittest.main()
