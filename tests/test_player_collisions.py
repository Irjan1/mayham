"""Surface normals, separation and the existing player movement rules."""

from collections import defaultdict
import math
import os
import unittest
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame

from config import GRAVITY, HEIGHT, PLAYER_RADIUS, WIDTH
from src.game_events import GameEvents
from src.geometry import circle_intersects_rect, circle_rect_contact
from src.objects import Obstacle
from src.player import Player1, Player2


class CircleRectangleContactTests(unittest.TestCase):
    def setUp(self):
        self.rect = pygame.Rect(100, 100, 80, 60)

    def test_faces_return_outward_unit_normals_and_overlap_depth(self):
        for center, expected_normal in (
            ((90, 130), (-1, 0)), ((190, 130), (1, 0)),
            ((140, 90), (0, -1)), ((140, 170), (0, 1)),
        ):
            with self.subTest(center=center):
                normal, depth = circle_rect_contact(center, PLAYER_RADIUS, self.rect)
                self.assertEqual(normal, expected_normal)
                self.assertEqual(depth, 8)

    def test_all_four_corners_return_radial_normals(self):
        for center, expected in (
            ((88, 91), (-0.8, -0.6)), ((192, 91), (0.8, -0.6)),
            ((192, 169), (0.8, 0.6)), ((88, 169), (-0.8, 0.6)),
        ):
            with self.subTest(center=center):
                normal, depth = circle_rect_contact(center, PLAYER_RADIUS, self.rect)
                self.assertAlmostEqual(normal[0], expected[0])
                self.assertAlmostEqual(normal[1], expected[1])
                self.assertAlmostEqual(math.hypot(*normal), 1)
                self.assertAlmostEqual(depth, 3)

    def test_inside_or_on_face_uses_nearest_exit_without_dividing_by_zero(self):
        for center, expected_normal, expected_depth in (
            ((110, 130), (-1, 0), 28), ((170, 130), (1, 0), 28),
            ((140, 110), (0, -1), 28), ((140, 150), (0, 1), 28),
            ((100, 130), (-1, 0), 18), ((140, 130), (0, -1), 48),
            ((100, 100), (-1, 0), 18),
        ):
            with self.subTest(center=center):
                self.assertEqual(circle_rect_contact(center, PLAYER_RADIUS, self.rect),
                                 (expected_normal, expected_depth))

    def test_contact_matches_existing_detection_and_tangency_rules(self):
        for center in ((82, 130), (83, 130), (82.5, 130), (87, 87), (88, 88),
                       (140, 82), (198, 130), (140, 178), (120, 120), (50, 50)):
            with self.subTest(center=center):
                self.assertEqual(circle_rect_contact(center, PLAYER_RADIUS, self.rect) is not None,
                                 circle_intersects_rect(center, PLAYER_RADIUS, self.rect))


class PlayerCollisionTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.player = Player1(0, 0)
        self.block = Obstacle(100, 100, (80, 60), 'white')

    def tearDown(self):
        pygame.quit()

    def test_face_bounces_preserve_tangential_velocity_and_speed(self):
        for center, incoming, expected, position in (
            ((90, 130), (4, 3), (-4, 3), (82, 130)),
            ((190, 130), (-4, 3), (4, 3), (198, 130)),
            ((140, 90), (4, 3), (4, -3), (140, 82)),
            ((140, 170), (4, -3), (4, 3), (140, 178)),
        ):
            with self.subTest(center=center):
                self.player.x, self.player.y = center
                self.player.vx, self.player.vy = incoming
                self.assertTrue(self.player.resolve_obstacle_collisions([self.block]))
                self.assertEqual((self.player.vx, self.player.vy), expected)
                self.assertAlmostEqual(self.player.x, position[0], places=5)
                self.assertAlmostEqual(self.player.y, position[1], places=5)
                self.assertFalse(self.player.collision(self.block))
                self.assertEqual(self.player.rect.center, (round(self.player.x), round(self.player.y)))

    def test_corner_bounce_has_natural_angle_and_preserves_speed(self):
        self.player.x, self.player.y = 88, 91
        self.player.vx, self.player.vy = 7, 4
        self.player.resolve_obstacle_collisions([self.block])
        self.assertAlmostEqual(self.player.vx, -5.8)
        self.assertAlmostEqual(self.player.vy, -5.6)
        self.assertAlmostEqual(self.player.vx ** 2 + self.player.vy ** 2, 65)
        self.assertFalse(self.player.collision(self.block))

    def test_outward_tangential_and_stationary_velocity_do_not_reverse(self):
        for center, velocity in (
            ((90, 130), (-4, 3)), ((90, 130), (0, 3)), ((90, 130), (0, 0)),
            ((88, 91), (-7, -4)), ((88, 91), (3, -4)),
        ):
            with self.subTest(center=center, velocity=velocity):
                self.player.x, self.player.y = center
                self.player.vx, self.player.vy = velocity
                self.player.resolve_obstacle_collisions([self.block])
                self.assertAlmostEqual(self.player.vx, velocity[0])
                self.assertAlmostEqual(self.player.vy, velocity[1])
                self.assertFalse(self.player.collision(self.block))

    def test_exact_tangency_does_not_move_or_bounce_player(self):
        self.player.x, self.player.y = 82, 130
        self.player.vx, self.player.vy = 4, 3
        self.assertFalse(self.player.resolve_obstacle_collisions([self.block]))
        self.assertEqual((self.player.x, self.player.y, self.player.vx, self.player.vy), (82, 130, 4, 3))

    def test_embedded_center_is_separated_and_only_inward_velocity_reflects(self):
        for vx in (5, -5, 0):
            with self.subTest(vx=vx):
                self.player.x, self.player.y = 110, 130
                self.player.vx, self.player.vy = vx, 3
                self.player.resolve_obstacle_collisions([self.block])
                self.assertAlmostEqual(self.player.x, 82, places=5)
                self.assertEqual(self.player.vx, -abs(vx))
                self.assertEqual(self.player.vy, 3)
                self.assertFalse(self.player.collision(self.block))

    def test_l_inner_corner_resolves_both_contacts_in_either_order(self):
        left = Obstacle(100, 100, (20, 100), 'white')
        bottom = Obstacle(120, 180, (80, 20), 'white')
        for parts in ([left, bottom], [bottom, left]):
            self.player.x, self.player.y = 132, 168
            self.player.vx, self.player.vy = -3, 4
            self.player.resolve_obstacle_collisions(parts)
            self.assertFalse(any(self.player.collision(part) for part in parts))
            self.assertEqual((self.player.vx, self.player.vy), (3, -4))
            position = (self.player.x, self.player.y)
            self.assertFalse(self.player.resolve_obstacle_collisions(parts))
            self.assertEqual((self.player.x, self.player.y), position)
            self.assertEqual((self.player.vx, self.player.vy), (3, -4))

    def test_center_on_shared_internal_seam_does_not_get_stuck(self):
        top = Obstacle(100, 100, (40, 100), 'white')
        bottom = Obstacle(100, 200, (40, 100), 'white')
        for parts in ([top, bottom], [bottom, top]):
            self.player.x, self.player.y = 120, 200
            self.player.vx, self.player.vy = 5, 0
            self.player.resolve_obstacle_collisions(parts)
            self.assertFalse(any(self.player.collision(part) for part in parts))
            self.assertFalse(self.player.resolve_obstacle_collisions(parts))
            self.assertAlmostEqual(self.player.vx ** 2 + self.player.vy ** 2, 25)

    def test_u_inside_corners_separate_from_each_arm(self):
        parts = [Obstacle(100, 100, (24, 140), 'white'),
                 Obstacle(124, 216, (112, 24), 'white'),
                 Obstacle(236, 100, (24, 140), 'white')]
        for center, incoming, expected in (
            ((136, 204), (-3, 4), (3, -4)), ((224, 204), (3, 4), (-3, -4)),
        ):
            with self.subTest(center=center):
                self.player.x, self.player.y = center
                self.player.vx, self.player.vy = incoming
                self.player.resolve_obstacle_collisions(parts)
                self.assertFalse(any(self.player.collision(part) for part in parts))
                self.assertEqual((self.player.vx, self.player.vy), expected)

    def test_screen_faces_keep_quarter_strength_and_do_not_reverse_outgoing_motion(self):
        for center, incoming, expected, position in (
            ((10, 300), (-8, 3), (2, 3), (PLAYER_RADIUS, 300)),
            ((WIDTH - 10, 300), (8, 3), (-2, 3), (WIDTH - PLAYER_RADIUS, 300)),
            ((300, 10), (3, -8), (3, 2), (300, PLAYER_RADIUS)),
            ((300, HEIGHT - 10), (3, 8), (3, -2), (300, HEIGHT - PLAYER_RADIUS)),
            ((10, 300), (8, 3), (8, 3), (PLAYER_RADIUS, 300)),
            ((300, HEIGHT - 10), (3, -8), (3, -8), (300, HEIGHT - PLAYER_RADIUS)),
            ((10, 10), (-8, -12), (2, 3), (PLAYER_RADIUS, PLAYER_RADIUS)),
        ):
            with self.subTest(center=center, incoming=incoming):
                self.player.x, self.player.y = center
                self.player.vx, self.player.vy = incoming
                self.player.inside_screen()
                self.assertEqual((self.player.x, self.player.y), position)
                self.assertEqual((self.player.vx, self.player.vy), expected)

    def test_free_movement_and_gravity_are_unchanged(self):
        self.player.x, self.player.y = 300, 300
        self.player.vx, self.player.vy = 3, 4
        self.player.update(defaultdict(bool), [], pygame.sprite.Group(self.player),
                           pygame.sprite.Group(), pygame.sprite.Group(), GameEvents())
        self.assertEqual(self.player.radius, 18)
        self.assertEqual(self.player.gravity, GRAVITY)
        self.assertEqual(self.player.x, 303)
        self.assertAlmostEqual(self.player.y, 304 + GRAVITY)
        self.assertAlmostEqual(self.player.vy, 4 + GRAVITY)
        self.assertEqual(self.player.vx, 3)

    def test_resting_contact_under_gravity_does_not_add_bounce_energy(self):
        self.player.x, self.player.y = 140, 100 - PLAYER_RADIUS
        players = pygame.sprite.Group(self.player)
        for _ in range(120):
            self.player.update(defaultdict(bool), [self.block], players,
                               pygame.sprite.Group(), pygame.sprite.Group(), GameEvents())
            self.assertFalse(self.player.collision(self.block))
            self.assertLess(abs(self.player.vy), 0.1)
            self.assertAlmostEqual(self.player.y, 100 - PLAYER_RADIUS, places=4)

    def test_wall_damage_cooldown_is_preserved_across_multiple_contacts(self):
        events = GameEvents()
        players = pygame.sprite.Group(self.player, Player2(900, 600))
        with patch('src.game_events.WALL_DAMAGE', 5):
            for ticks, health in ((1000, 95), (1100, 95), (1500, 90)):
                self.player.x, self.player.y = 140, 90
                self.player.vx, self.player.vy = 0, 3
                with patch('pygame.time.get_ticks', return_value=ticks):
                    self.player.update(defaultdict(bool), [self.block], players,
                                       pygame.sprite.Group(), pygame.sprite.Group(), events)
                self.assertEqual(self.player.needs.health, health)

    def test_destructible_blocks_bounce_players_until_removed(self):
        block = Obstacle(100, 100, (80, 60), 'white', destructible=True)
        parts = pygame.sprite.Group(block)
        self.player.x, self.player.y = 90, 130
        self.player.vx, self.player.vy = 4, 3
        durability = block.hits_remaining
        self.player.resolve_obstacle_collisions(parts)
        self.assertEqual((self.player.vx, self.player.vy), (-4, 3))
        self.assertEqual(block.hits_remaining, durability)
        for _ in range(durability):
            block.take_bullet_hit()
        self.player.x, self.player.y = 90, 130
        self.assertFalse(self.player.resolve_obstacle_collisions(parts))

    def test_ship_collision_rewind_cannot_leave_player_inside_obstacle(self):
        self.player.x, self.player.y = 90, 130
        opponent = Player2(70, 130)
        self.player.update(defaultdict(bool), [self.block], pygame.sprite.Group(self.player, opponent),
                           pygame.sprite.Group(), pygame.sprite.Group(), GameEvents())
        self.assertFalse(self.player.collision(self.block))


if __name__ == '__main__':
    unittest.main()
