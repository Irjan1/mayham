"""Cosmetic surfaces retain geometry, caching and independent randomness."""

import random
import unittest
from unittest.mock import patch

import pygame

from src.block_art import create_block_surface
from src.hazard_art import draw_hazard
from src.objects import Hazard, Obstacle


class EnvironmentArtTests(unittest.TestCase):
    def test_small_large_and_thin_blocks_keep_geometry_in_every_damage_stage(self):
        state = random.getstate()
        for size in ((1, 1), (8, 5), (24, 240), (360, 24), (160, 160)):
            for destructible in (False, True):
                with self.subTest(size=size, destructible=destructible):
                    block = Obstacle(123, 234, size, 'white', destructible=destructible)
                    original_rect = block.rect.copy()
                    group = pygame.sprite.Group(block)
                    images = []
                    for damage in range(3):
                        self.assertEqual(block.rect, original_rect)
                        self.assertEqual(block.image.get_size(), size)
                        images.append(pygame.image.tobytes(block.image, 'RGB'))
                        block.take_bullet_hit()
                    if destructible:
                        self.assertNotIn(block, group)
                        if min(size) >= 8:
                            self.assertEqual(len(set(images)), 3)
                    else:
                        self.assertIn(block, group)
                        self.assertEqual(len(set(images)), 1)
        self.assertEqual(random.getstate(), state)

    def test_texture_is_repeatable_and_cached_until_damage_changes(self):
        with patch('src.objects.create_block_surface', wraps=create_block_surface) as paint:
            block = Obstacle(100, 200, (80, 80), 'white', destructible=True)
            cached = block.image
            for _ in range(5):
                block.update()
            self.assertIs(block.image, cached)
            self.assertEqual(paint.call_count, 1)
            same = create_block_surface(block.rect, destructible=True)
            self.assertEqual(pygame.image.tobytes(cached, 'RGB'), pygame.image.tobytes(same, 'RGB'))
            block.take_bullet_hit()
            self.assertEqual(paint.call_count, 2)
            self.assertIsNot(block.image, cached)

    def test_spikes_keep_size_and_drawing_stays_inside_zone_and_clip(self):
        for size in ((1, 1), (8, 5), (112, 32), (200, 64)):
            rect = pygame.Rect(20, 20, *size)
            hazard = Hazard(rect)
            self.assertEqual(hazard.rect, rect)
            self.assertEqual(hazard.image.get_size(), size)
            screen = pygame.Surface((260, 120))
            screen.fill((1, 2, 3))
            clip = pygame.Rect(22, 22, 220, 80)
            screen.set_clip(clip)
            draw_hazard(screen, rect)
            self.assertEqual(screen.get_clip(), clip)
            self.assertEqual(screen.get_at((19, 20))[:3], (1, 2, 3))
            self.assertEqual(screen.get_at((20, 20))[:3], (1, 2, 3))


if __name__ == '__main__':
    unittest.main()
