"""Cosmetic events, particle limits and unchanged gameplay with effects enabled."""

from collections import defaultdict
import os
import random
import unittest
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame

from config import FPS, FUEL_COLOR, FUEL_SIZE
from main import Game
from src.arena import ArenaLayout
from src.effects import MAX_PARTICLES, ParticleEffects
from src.game_events import GameEvents
from src.objects import Bullet, Fuel, Obstacle
from src.player import Player1


class ParticleTests(unittest.TestCase):
    def test_particles_move_and_expire_without_collision_sprites(self):
        effects = ParticleEffects(42)
        effects.add((100, 200), (10, -20), (255, 180, 80), 2, 0.2)
        effects.update(0.1)
        particle = effects.particles[0]
        self.assertEqual((particle.x, particle.y), (101, 198))
        self.assertAlmostEqual(particle.age, 0.1)
        self.assertNotIsInstance(particle, pygame.sprite.Sprite)
        effects.update(0.1)
        self.assertEqual(effects.particles, [])

    def test_all_emitters_share_a_hard_cap_and_short_lifetimes(self):
        effects = ParticleEffects(42)
        player = Player1(100, 100)
        bullet = Bullet(200, 200, 0, player)
        for _ in range(100):
            effects.exhaust(player)
            effects.trail(bullet)
            effects.impact((300, 300), (-1, 0))
            effects.debris(pygame.Rect(300, 300, 80, 80))
            self.assertLessEqual(len(effects.particles), MAX_PARTICLES)
        self.assertEqual(len(effects.particles), MAX_PARTICLES)
        effects.update(0.5)
        self.assertEqual(effects.particles, [])
        effects.exhaust(player)
        self.assertTrue(effects.particles)

    def test_continuous_exhaust_and_many_trails_stay_bounded(self):
        effects = ParticleEffects(42)
        player = Player1(100, 100)
        bullet = Bullet(200, 200, 0, player)
        for _ in range(300):
            effects.update(1 / 60)
            effects.exhaust(player)
            effects.exhaust(player)
            for _ in range(30):
                effects.trail(bullet)
            self.assertLessEqual(len(effects.particles), MAX_PARTICLES)
        effects.clear()
        self.assertEqual(effects.particles, [])

    def test_cosmetic_randomness_is_local_and_repeatable(self):
        state = random.getstate()
        first, second = ParticleEffects('cosmetics'), ParticleEffects('cosmetics')
        for effects in (first, second):
            effects.exhaust(Player1(100, 200))
            effects.impact((300, 400), (-1, 0))
            effects.debris(pygame.Rect(400, 300, 80, 80))
        self.assertEqual(first.particles, second.particles)
        self.assertEqual(random.getstate(), state)

    def test_drawing_does_not_advance_or_change_particles(self):
        effects = ParticleEffects(42)
        effects.add((50, 50), (10, 20), (255, 180, 80), 2, 0.2)
        before = vars(effects.particles[0]).copy()
        screen = pygame.Surface((100, 100))
        effects.draw(screen)
        effects.draw(screen)
        self.assertEqual(vars(effects.particles[0]), before)
        self.assertNotEqual(tuple(screen.get_at((50, 50)))[:3], (0, 0, 0))


class EffectEventTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.saved_scores = GameEvents.get_scores()
        GameEvents.player_scores.update(Player1=0, Player2=0)
        self.effects = ParticleEffects(42)
        self.player = Player1(100, 100)
        self.player.effects = self.effects

    def tearDown(self):
        GameEvents.player_scores.clear()
        GameEvents.player_scores.update(self.saved_scores)
        pygame.quit()

    def test_exhaust_only_emits_while_thrust_is_actually_applied(self):
        keys = defaultdict(bool)
        bullets = pygame.sprite.Group()
        self.player.handle_input(keys, bullets)
        self.assertEqual(self.effects.particles, [])
        keys[self.player.controls['up']] = True
        self.player.needs.fuel = 0
        self.player.handle_input(keys, bullets)
        self.assertEqual(self.effects.particles, [])
        self.player.needs.fuel = 100
        self.player.handle_input(keys, bullets)
        self.assertTrue(self.effects.particles)
        self.assertTrue(all(particle.y > self.player.y for particle in self.effects.particles))

    def test_fired_bullets_share_the_cosmetic_emitter(self):
        bullets = pygame.sprite.Group()
        with patch('pygame.time.get_ticks', return_value=1000):
            self.player.shoot(bullets)
        bullet = next(iter(bullets))
        self.assertIs(bullet.effects, self.effects)
        bullet.vx = bullet.vy = 0
        bullet.update([], [], GameEvents())
        self.assertEqual(self.effects.particles, [])
        bullet.vx = 100
        bullet.update([], [], GameEvents())
        # One trail mark per frame, independent of projectile collision substeps.
        self.assertEqual(len(self.effects.particles), 1)

    def test_sparks_emit_once_at_terminal_obstacle_contact(self):
        block = Obstacle(200, 100, (20, 80), 'white')
        bullet = Bullet(190, 140, 0, self.player, effects=self.effects)
        bullet.vx, bullet.vy = 10, 0
        bullet.update([], [block], GameEvents())
        self.assertTrue(bullet.finished)
        self.assertGreater(len(self.effects.particles), 1)
        sparks = self.effects.particles[1:]
        self.assertTrue(all(abs(particle.x - block.rect.left) < 1e-5 for particle in sparks))
        self.assertTrue(all(particle.vx < 0 for particle in sparks))
        count = len(self.effects.particles)
        bullet.update([], [block], GameEvents())
        self.assertEqual(len(self.effects.particles), count)

    def test_ricochet_emits_sparks_but_outgoing_overlap_does_not(self):
        block = Obstacle(200, 100, (20, 80), 'white')
        incoming = Bullet(197, 140, 0, self.player, bounces=1, effects=self.effects)
        incoming.vx, incoming.vy = 3, 0
        incoming.update([], [block], GameEvents())
        self.assertGreater(len(self.effects.particles), 1)
        self.assertEqual(incoming.bounces_remaining, 0)
        self.assertFalse(incoming.finished)
        self.effects.clear()
        outgoing = Bullet(197, 140, 0, self.player, bounces=1, effects=self.effects)
        outgoing.vx, outgoing.vy = -3, 0
        outgoing.update([], [block], GameEvents())
        self.assertEqual(len(self.effects.particles), 1)  # Trail only.
        self.assertEqual(outgoing.bounces_remaining, 1)

    def test_debris_emits_only_when_destructible_block_breaks(self):
        block = Obstacle(200, 100, (80, 80), 'white', destructible=True, effects=self.effects)
        obstacles = pygame.sprite.Group(block)
        block.take_bullet_hit()
        block.take_bullet_hit()
        self.assertEqual(self.effects.particles, [])
        self.assertIn(block, obstacles)
        block.take_bullet_hit()
        self.assertTrue(self.effects.particles)
        self.assertEqual(block.hits_remaining, 0)
        self.assertNotIn(block, obstacles)
        self.effects.clear()
        solid = Obstacle(200, 100, (80, 80), 'white', effects=self.effects)
        solid.take_bullet_hit()
        self.assertEqual(self.effects.particles, [])

    def test_particles_draw_behind_rockets_and_fuel(self):
        game = Game(seed=42, fixed_arena=True)
        fuel = Fuel(300, 100, FUEL_SIZE, FUEL_COLOR)
        game.fuel_cans.add(fuel)
        game.all_sprites.add(fuel)
        positions = (game.player1.rect.center, fuel.rect.center)
        game.draw()
        expected_colors = [game.screen.get_at(position) for position in positions]
        for position in positions:
            game.effects.add(position, (0, 0), (255, 255, 255), 14, 1)
        game.draw()
        self.assertEqual([game.screen.get_at(position) for position in positions], expected_colors)

    def test_exhaust_stays_behind_the_nozzle_at_each_ship_heading(self):
        for angle, backward in ((0, (0, 1)), (90, (1, 0)), (180, (0, -1)), (270, (-1, 0))):
            with self.subTest(angle=angle):
                self.effects.clear()
                self.player.angle = angle
                self.player.vx, self.player.vy = 2, -1
                self.effects.exhaust(self.player)
                for particle in self.effects.particles:
                    offset_x, offset_y = particle.x - self.player.x, particle.y - self.player.y
                    self.assertGreaterEqual(offset_x * backward[0] + offset_y * backward[1], 17)
                    relative_vx = particle.vx - self.player.vx * FPS
                    relative_vy = particle.vy - self.player.vy * FPS
                    self.assertGreater(relative_vx * backward[0] + relative_vy * backward[1], 0)

    def test_heavy_cosmetic_use_does_not_change_arena_or_gameplay_random_streams(self):
        first = Game(seed=42)
        states = (first.style_rng.getstate(), first.fuel_rng.getstate(), first.upgrade_rng.getstate())
        for _ in range(100):
            first.effects.exhaust(first.player1)
            first.effects.impact((300, 300), (-1, 0))
            first.effects.debris(pygame.Rect(300, 300, 80, 80))
        self.assertEqual(states, (first.style_rng.getstate(), first.fuel_rng.getstate(),
                                  first.upgrade_rng.getstate()))
        first.start_new_round()
        expected = first.arena
        self.assertEqual(first.effects.particles, [])
        second = Game(seed=42)
        second.start_new_round()
        self.assertEqual(second.arena, expected)

    def test_effects_pause_with_upgrade_screen(self):
        game = Game(seed=42, fixed_arena=True)
        game.effects.add((300, 300), (10, 20), (255, 180, 80), 2, 0.2)
        before = vars(game.effects.particles[0]).copy()
        game.upgrade_player = 'Player2'
        game.update_game()
        self.assertEqual(vars(game.effects.particles[0]), before)

    def test_gameplay_results_match_with_or_without_cosmetic_hooks(self):
        def play(effects_enabled):
            game = Game(seed=42, fixed_arena=True)
            block = pygame.Rect(500, 200, 24, 220)
            game.game_objects(ArenaLayout([block], (200, 220), (900, 600),
                                          destructible_obstacles=[block]))
            game.player1.angle = 270
            if not effects_enabled:
                for sprite in (*game.players, *game.obstacles):
                    sprite.effects = None
            keys = defaultdict(bool)
            keys[game.player1.controls['up']] = True
            keys[game.player1.controls['shoot']] = True
            with patch('pygame.key.get_pressed', return_value=keys):
                for frame in range(80):
                    with patch('pygame.time.get_ticks', return_value=1000 + frame * 16):
                        game.update_game()
            self.assertEqual(len(game.obstacles), 0)
            return (
                [(p.x, p.y, p.vx, p.vy, p.needs.health, p.needs.fuel) for p in game.players],
                [(b.x, b.y, b.vx, b.vy, b.radius, b.damage, b.bounces_remaining) for b in game.bullets],
                game.game_events.get_scores(), len(game.fuel_cans), game.fuel_rng.getstate(),
            )
        self.assertEqual(play(True), play(False))


if __name__ == '__main__':
    unittest.main()
