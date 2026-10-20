"""Direct gameplay checks for destructible blocks and lethal spike zones."""

import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from config import BULLET_DAMAGE, DESTRUCTIBLE_HITS, FUEL_SIZE, OBSTACLE_COLOR
from main import Game
from src.arena import ArenaLayout, get_fuel_positions, rectangle_fits, validate_arena
from src.game_events import GameEvents
from src.objects import Bullet, Obstacle
from src.player import Player1, Player2


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.saved_scores = GameEvents.player_scores.copy()
        GameEvents.player_scores.update(Player1=0, Player2=0)

    def tearDown(self):
        GameEvents.player_scores.clear()
        GameEvents.player_scores.update(self.saved_scores)
        pygame.quit()

    def test_three_bullets_destroy_block_and_remove_all_group_memberships(self):
        block = Obstacle(300, 200, (80, 80), OBSTACLE_COLOR, destructible=True)
        obstacles = pygame.sprite.Group(block)
        drawing = pygame.sprite.Group(block)
        bullets = pygame.sprite.Group()
        owner = Player1(100, 100)
        events = GameEvents()
        original_image = pygame.image.tostring(block.image, 'RGB')

        for hit in range(1, DESTRUCTIBLE_HITS + 1):
            bullet = Bullet(*block.rect.center, 0, owner)
            bullet.vx = bullet.vy = 0
            bullets.add(bullet)
            drawing.add(bullet)
            bullet.update([], obstacles, events)
            self.assertEqual(bullet.groups(), [])
            self.assertEqual(block.hits_remaining, DESTRUCTIBLE_HITS - hit)
            if hit < DESTRUCTIBLE_HITS:
                self.assertIn(block, obstacles)
                self.assertNotEqual(pygame.image.tostring(block.image, 'RGB'), original_image)

        self.assertEqual(block.groups(), [])
        self.assertEqual(len(obstacles), 0)
        self.assertEqual(len(drawing), 0)
        self.assertEqual(len(bullets), 0)

    def test_permanent_obstacle_stops_bullets_without_breaking(self):
        block = Obstacle(300, 200, (80, 80), OBSTACLE_COLOR)
        obstacles = pygame.sprite.Group(block)
        for _ in range(5):
            bullet = Bullet(*block.rect.center, 0, Player1(100, 100))
            bullet.vx = bullet.vy = 0
            bullets = pygame.sprite.Group(bullet)
            bullet.update([], obstacles, GameEvents())
            self.assertEqual(len(bullets), 0)
        self.assertIn(block, obstacles)

    def test_one_bullet_only_damages_one_touching_part(self):
        first = Obstacle(300, 200, (80, 80), OBSTACLE_COLOR, destructible=True)
        second = Obstacle(380, 200, (80, 80), OBSTACLE_COLOR, destructible=True)
        obstacles = pygame.sprite.Group(first, second)
        bullet = Bullet(380, 240, 0, Player1(100, 100))
        bullet.vx = bullet.vy = 0
        bullet.update([], obstacles, GameEvents())

        self.assertEqual(first.hits_remaining, DESTRUCTIBLE_HITS - 1)
        self.assertEqual(second.hits_remaining, DESTRUCTIBLE_HITS)

    def test_bullet_that_hit_player_does_not_also_damage_a_block(self):
        owner, target = Player1(100, 100), Player2(340, 240)
        block = Obstacle(300, 200, (80, 80), OBSTACLE_COLOR, destructible=True)
        bullet = Bullet(target.x, target.y, 0, owner)
        bullet.vx = bullet.vy = 0
        bullet.update([owner, target], pygame.sprite.Group(block), GameEvents())

        self.assertEqual(target.needs.health, 100 - BULLET_DAMAGE)
        self.assertEqual(block.hits_remaining, DESTRUCTIBLE_HITS)

    def test_spike_contact_uses_circle_and_awards_opponent_once(self):
        game = Game(seed=42, fixed_arena=True)
        rect = pygame.Rect(300, 400, 100, 32)
        game.game_objects(ArenaLayout([], (100, 100), (900, 600), hazards=[rect]))
        game.player1.x = rect.left - game.player1.radius + 1
        game.player1.y = rect.centery
        game.player1.update_rect()
        player = game.player1

        game.update_game()

        self.assertEqual(player.needs.health, 0)
        self.assertFalse(player.is_alive)
        self.assertEqual(player.groups(), [])
        self.assertIs(game.game_events.get_game_winner(), game.player2)
        self.assertEqual(GameEvents.get_scores(), {"Player1": 0, "Player2": 1})
        game.update_game()
        self.assertEqual(GameEvents.get_scores(), {"Player1": 0, "Player2": 1})

    def test_exact_circle_tangency_to_spikes_is_not_contact(self):
        game = Game(seed=42, fixed_arena=True)
        rect = pygame.Rect(300, 400, 100, 32)
        game.game_objects(ArenaLayout([], (100, 100), (900, 600), hazards=[rect]))
        game.player1.x = rect.left - game.player1.radius
        game.player1.y = rect.centery
        game.player1.update_rect()

        game.update_game()

        self.assertTrue(game.player1.is_alive)
        self.assertEqual(game.player1.needs.health, 100)
        self.assertIsNone(game.game_events.get_game_winner())
        self.assertNotIn(next(iter(game.hazards)), game.obstacles)

    def test_hazards_are_cleared_between_rounds(self):
        game = Game(seed=42, fixed_arena=True)
        game.game_objects(ArenaLayout([], (100, 100), (900, 600),
                                      hazards=[pygame.Rect(300, 400, 100, 32)]))
        hazard = next(iter(game.hazards))
        self.assertIn(hazard, game.all_sprites)

        game.start_new_round()

        self.assertEqual(hazard.groups(), [])
        self.assertEqual(len(game.hazards), 0)

    def test_game_refreshes_fuel_positions_after_bullet_destroys_block(self):
        game = Game(seed=42, fixed_arena=True)
        rect = pygame.Rect(460, 280, 160, 160)
        hazard = pygame.Rect(750, 440, 100, 32)
        arena = ArenaLayout([rect], (270, 180), (810, 540), hazards=[hazard],
                            destructible_obstacles=[rect])
        self.assertTrue(validate_arena(arena))
        game.game_objects(arena)
        block = next(iter(game.obstacles))
        for _ in range(DESTRUCTIBLE_HITS - 1):
            block.take_bullet_hit()
        before = game.fuel_positions
        bullet = Bullet(*rect.center, 0, game.player1)
        bullet.vx = bullet.vy = 0
        game.bullets.add(bullet)

        game.update_game()

        self.assertEqual(block.groups(), [])
        self.assertEqual(bullet.groups(), [])
        self.assertEqual(game.fuel_positions, get_fuel_positions(arena, obstacles=[]))
        self.assertGreater(len(game.fuel_positions), len(before))
        self.assertTrue(any(pygame.Rect(position, FUEL_SIZE).colliderect(rect)
                            for position in game.fuel_positions))
        self.assertTrue(all(rectangle_fits(pygame.Rect(position, FUEL_SIZE), [hazard])
                            for position in game.fuel_positions))
        self.assertEqual(arena.obstacles, [rect])

    def test_game_honors_selected_style_and_destructible_flags(self):
        for style in ("open", "corridors", "scattered"):
            with self.subTest(style=style):
                game = Game(seed=42, style=style)
                self.assertEqual(game.arena.style, style)
                for obstacle in game.obstacles:
                    self.assertEqual(obstacle.destructible,
                                     obstacle.rect in game.arena.destructible_obstacles)
                self.assertEqual([hazard.rect for hazard in game.hazards], game.arena.hazards)
                game.start_new_round()
                self.assertEqual(game.arena.style, style)


if __name__ == "__main__":
    unittest.main()
