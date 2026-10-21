"""Observable projectile behavior and combinations of the four new upgrades."""

import math
import os
import unittest
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame

from config import DESTRUCTIBLE_HITS, EXPLOSION_LIFETIME, HEIGHT, WIDTH
from main import Game
from src.arena import ArenaLayout
from src.game_events import GameEvents
from src.objects import Bullet, Explosion, Obstacle
from src.upgrades import UPGRADES, create_upgrade_levels
from src.player import Player1, Player2


class ProjectileTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.saved_scores = GameEvents.get_scores()
        GameEvents.player_scores.update(Player1=0, Player2=0)
        self.owner = Player1(50, 500)
        self.target = Player2(900, 500)
        self.players = pygame.sprite.Group(self.owner, self.target)
        self.obstacles = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.explosions = pygame.sprite.Group()
        self.events = GameEvents()

    def tearDown(self):
        GameEvents.player_scores.clear()
        GameEvents.player_scores.update(self.saved_scores)
        pygame.quit()

    def make_bullet(self, x, y, vx=0, vy=0, **upgrades):
        bullet = Bullet(x, y, 0, self.owner, **upgrades)
        bullet.vx, bullet.vy = vx, vy
        self.bullets.add(bullet)
        return bullet

    def update_bullets(self):
        self.bullets.update(self.players, self.obstacles, self.events, self.explosions)

    def test_both_size_levels_match_visuals_and_leave_damage_unchanged(self):
        for level, radius in ((1, 5), (2, 6)):
            with self.subTest(level=level):
                levels = create_upgrade_levels()
                levels['larger_bullets'] = level
                self.owner.apply_upgrades(levels)
                with patch('pygame.time.get_ticks', return_value=1000 * level):
                    self.owner.shoot(self.bullets)
                bullet = list(self.bullets)[-1]
                self.assertEqual(bullet.radius, radius)
                self.assertEqual(bullet.rect.size, (2 * radius, 2 * radius))
                self.assertEqual(bullet.image.get_size(), bullet.rect.size)
                self.assertEqual(bullet.image.get_bounding_rect().size, bullet.rect.size)
                self.assertEqual(bullet.damage, 20)

    def test_larger_hitbox_can_hit_where_a_base_bullet_misses(self):
        self.target.x, self.target.y = 200, 200
        small = self.make_bullet(177.5, 200)
        self.update_bullets()
        self.assertFalse(small.finished)
        large = self.make_bullet(177.5, 200, radius=5)
        self.update_bullets()
        self.assertTrue(large.finished)
        self.assertEqual(self.target.needs.health, 80)

    def test_heavy_damage_at_both_levels_is_based_on_original_damage(self):
        for level, damage in ((1, 24), (2, 28)):
            with self.subTest(level=level):
                levels = create_upgrade_levels()
                levels['heavy_bullets'] = level
                for _ in range(3):
                    self.owner.apply_upgrades(levels)
                self.owner.x, self.owner.y = self.target.x, self.target.y
                with patch('pygame.time.get_ticks', return_value=1000 * level):
                    self.owner.shoot(self.bullets)
                bullet = list(self.bullets)[-1]
                self.assertEqual(bullet.damage, damage)
                self.target.needs.health = 100
                self.update_bullets()
                self.assertEqual(self.target.needs.health, 100 - damage)
                bullet.update(self.players, self.obstacles, self.events, self.explosions)
                self.assertEqual(self.target.needs.health, 100 - damage)

    def test_shooters_have_independent_stats_and_fired_bullets_keep_their_stats(self):
        levels = create_upgrade_levels()
        levels.update(larger_bullets=2, heavy_bullets=1, ricochet=2, explosive_rounds=1)
        self.owner.apply_upgrades(levels)
        with patch('pygame.time.get_ticks', return_value=1000):
            self.owner.shoot(self.bullets)
            self.target.shoot(self.bullets)
        upgraded, normal = self.bullets
        self.assertEqual((upgraded.radius, upgraded.damage, upgraded.bounces_remaining,
                          upgraded.explosion_radius), (6, 24, 2, 48))
        self.assertEqual((normal.radius, normal.damage, normal.bounces_remaining,
                          normal.explosion_radius), (4, 20, 0, 0))
        self.owner.apply_upgrades(create_upgrade_levels())
        self.assertEqual((upgraded.radius, upgraded.damage, upgraded.bounces_remaining,
                          upgraded.explosion_radius), (6, 24, 2, 48))

    def test_ricochet_budget_allows_one_or_two_then_next_impact_removes_bullet(self):
        for budget in (1, 2):
            with self.subTest(budget=budget):
                bullet = self.make_bullet(WIDTH - 5, 300, 8, 0, bounces=budget)
                for hit in range(budget + 1):
                    bullet.x = WIDTH - 5 if hit % 2 == 0 else 5
                    bullet.vx = 8 if hit % 2 == 0 else -8
                    bullet.update(self.players, self.obstacles, self.events, self.explosions)
                    if hit < budget:
                        self.assertFalse(bullet.finished)
                        self.assertEqual(bullet.bounces_remaining, budget - hit - 1)
                        self.assertEqual(bullet.vx, -8 if hit % 2 == 0 else 8)
                        self.assertGreaterEqual(bullet.x, bullet.radius)
                        self.assertLessEqual(bullet.x, WIDTH - bullet.radius)
                    else:
                        self.assertTrue(bullet.finished)
                        self.assertNotIn(bullet, self.bullets)

    def test_vertical_and_horizontal_faces_preserve_tangential_velocity(self):
        block = Obstacle(100, 100, (80, 60), 'white')
        self.obstacles.add(block)
        for center, incoming, expected in (
            ((97, 130), (3, 2), (-3, 2)), ((183, 130), (-3, 2), (3, 2)),
            ((140, 97), (2, 3), (2, -3)), ((140, 163), (2, -3), (2, 3)),
        ):
            with self.subTest(center=center):
                bullet = self.make_bullet(*center, *incoming, bounces=1)
                bullet.update(self.players, self.obstacles, self.events, self.explosions)
                self.assertEqual((bullet.vx, bullet.vy), expected)
                self.assertEqual(bullet.bounces_remaining, 0)
                self.assertFalse(bullet.finished)
                self.assertFalse(bullet.collide_with_surfaces(self.obstacles))
                bullet.kill()

    def test_obstacle_corner_uses_radial_normal_and_preserves_speed(self):
        self.obstacles.add(Obstacle(100, 100, (80, 60), 'white'))
        bullet = self.make_bullet(97, 96, 4, 1, radius=6, bounces=1)
        self.update_bullets()
        self.assertAlmostEqual(bullet.vx, 0.16)
        self.assertAlmostEqual(bullet.vy, -4.12)
        self.assertAlmostEqual(math.hypot(bullet.vx, bullet.vy), math.sqrt(17))
        self.assertEqual(bullet.bounces_remaining, 0)
        self.assertFalse(bullet.finished)

    def test_horizontal_boundary_uses_larger_bullet_radius(self):
        bullet = self.make_bullet(300, HEIGHT - 7, 2, 8, radius=6, bounces=1)
        self.update_bullets()
        self.assertEqual((bullet.vx, bullet.vy), (2, -8))
        self.assertLessEqual(bullet.y + bullet.radius, HEIGHT)
        self.assertEqual(bullet.bounces_remaining, 0)

    def test_boundary_corner_counts_each_contacted_wall(self):
        bullet = self.make_bullet(WIDTH - 5, HEIGHT - 5, 3, 3, bounces=2)
        self.update_bullets()
        self.assertEqual((bullet.vx, bullet.vy), (-3, -3))
        self.assertEqual(bullet.bounces_remaining, 0)
        self.assertFalse(bullet.finished)

    def test_outgoing_overlap_separates_without_charging_another_bounce_or_hit(self):
        block = Obstacle(100, 100, (80, 60), 'white', destructible=True)
        self.obstacles.add(block)
        bullet = self.make_bullet(97, 130, -3, 2, bounces=1)
        self.update_bullets()
        self.assertEqual((bullet.vx, bullet.vy), (-3, 2))
        self.assertEqual(bullet.bounces_remaining, 1)
        self.assertEqual(block.hits_remaining, DESTRUCTIBLE_HITS)

    def test_ricochet_separates_and_does_not_repeatedly_hit_same_block(self):
        block = Obstacle(100, 100, (80, 60), 'white', destructible=True)
        self.obstacles.add(block)
        bullet = self.make_bullet(95, 130, 3, 0, radius=6, bounces=2, damage=28)
        for _ in range(5):
            self.update_bullets()
        self.assertEqual(bullet.bounces_remaining, 1)
        self.assertEqual(block.hits_remaining, DESTRUCTIBLE_HITS - 1)
        self.assertFalse(bullet.finished)

    def test_heavy_bullets_still_take_three_hits_to_break_blocks(self):
        block = Obstacle(100, 100, (80, 60), 'white', destructible=True)
        self.obstacles.add(block)
        for hit in range(DESTRUCTIBLE_HITS):
            bullet = self.make_bullet(140, 130, damage=28)
            self.update_bullets()
            self.assertTrue(bullet.finished)
            self.assertEqual(block.hits_remaining, DESTRUCTIBLE_HITS - hit - 1)
        self.assertNotIn(block, self.obstacles)

    def test_obstacle_wins_over_overlapping_player_and_only_takes_one_hit(self):
        block = Obstacle(300, 200, (80, 80), 'white', destructible=True)
        self.obstacles.add(block)
        self.target.x, self.target.y = 340, 240
        self.make_bullet(340, 240, damage=28)
        self.update_bullets()
        self.assertEqual(self.target.needs.health, 100)
        self.assertEqual(block.hits_remaining, DESTRUCTIBLE_HITS - 1)

    def test_fast_bullet_cannot_skip_a_one_pixel_wall_to_damage_player_behind_it(self):
        self.obstacles.add(Obstacle(200, 250, (1, 100), 'white'))
        self.target.x, self.target.y = 300, 300
        bullet = self.make_bullet(100, 300, 500, 0)
        self.update_bullets()
        self.assertTrue(bullet.finished)
        self.assertLess(bullet.x, 200)
        self.assertEqual(self.target.needs.health, 100)

    def test_player_in_front_of_wall_is_still_hit_first(self):
        block = Obstacle(220, 250, (20, 100), 'white', destructible=True)
        self.obstacles.add(block)
        self.target.x, self.target.y = 150, 300
        self.make_bullet(100, 300, 500, 0)
        self.update_bullets()
        self.assertEqual(self.target.needs.health, 80)
        self.assertEqual(block.hits_remaining, DESTRUCTIBLE_HITS)

    def test_fast_ricochet_uses_remaining_travel_in_reflected_direction(self):
        self.obstacles.add(Obstacle(200, 250, (1, 100), 'white'))
        bullet = self.make_bullet(100, 300, 120, 0, bounces=1)
        self.update_bullets()
        self.assertEqual(bullet.vx, -120)
        self.assertEqual(bullet.bounces_remaining, 0)
        self.assertLess(bullet.x, 196)
        self.assertFalse(bullet.finished)

    def test_blast_radius_includes_player_hitbox_and_excludes_shooter(self):
        self.owner.x, self.owner.y = 200, 200
        self.obstacles.add(Obstacle(198, 198, (4, 4), 'white'))
        for radius in (48, 72):
            for offset, expected_health in ((-1, 72), (1, 100)):
                with self.subTest(radius=radius, offset=offset):
                    self.target.needs.health = 100
                    self.target.x, self.target.y = 200 + radius + self.target.radius + offset, 200
                    self.make_bullet(200, 200, damage=28, explosion_radius=radius)
                    self.update_bullets()
                    self.assertEqual(self.target.needs.health, expected_health)
                    self.assertEqual(self.owner.needs.health, 100)
                    self.assertEqual(list(self.explosions)[-1].radius, radius)

    def test_explosive_direct_hit_replaces_direct_damage_and_cannot_repeat(self):
        self.target.x, self.target.y = 200, 200
        bullet = self.make_bullet(200, 200, damage=28, explosion_radius=48)
        self.update_bullets()
        for _ in range(5):
            bullet.update(self.players, self.obstacles, self.events, self.explosions)
            self.explosions.update()
        self.assertEqual(self.target.needs.health, 72)
        self.assertEqual(len(self.explosions), 1)
        self.assertTrue(bullet.finished)

    def test_explosion_kill_awards_owner_once_and_stops_other_bullets_after_round_end(self):
        self.target.x, self.target.y = 200, 200
        self.target.needs.health = 20
        self.make_bullet(200, 200, damage=28, explosion_radius=48)
        later = self.make_bullet(400, 300, 10, 0)
        self.update_bullets()
        self.update_bullets()
        self.assertEqual(self.target.needs.health, 0)
        self.assertFalse(self.target.is_alive)
        self.assertEqual(GameEvents.get_scores(), {'Player1': 1, 'Player2': 0})
        self.assertIs(self.events.get_game_winner(), self.owner)
        self.assertEqual(later.x, 400)

    def test_boundary_terminal_impact_also_explodes(self):
        self.make_bullet(WIDTH - 5, 300, 8, 0, explosion_radius=48)
        self.update_bullets()
        self.assertEqual(len(self.bullets), 0)
        self.assertEqual(len(self.explosions), 1)

    def test_ricochet_delays_explosion_until_terminal_surface_hit(self):
        bullet = self.make_bullet(WIDTH - 5, 300, 8, 0, bounces=1, explosion_radius=48)
        self.update_bullets()
        self.assertEqual(len(self.explosions), 0)
        bullet.x, bullet.vx = 5, -8
        self.update_bullets()
        self.assertTrue(bullet.finished)
        self.assertEqual(len(self.explosions), 1)

    def test_all_projectile_upgrades_work_together_and_explode_on_player_hit(self):
        levels = {upgrade_id: 2 for upgrade_id in UPGRADES}
        self.owner.apply_upgrades(levels)
        with patch('pygame.time.get_ticks', return_value=1000):
            self.owner.shoot(self.bullets)
        bullet = next(iter(self.bullets))
        bullet.x, bullet.y, bullet.vx, bullet.vy = 95, 130, 4, 0
        self.obstacles.add(Obstacle(100, 100, (80, 60), 'white'))
        self.target.x, self.target.y = 30, 130
        self.update_bullets()
        self.assertEqual((bullet.radius, bullet.damage, bullet.explosion_radius), (6, 28, 72))
        self.assertEqual(bullet.bounces_remaining, 1)
        self.assertEqual(len(self.explosions), 0)
        for _ in range(20):
            self.update_bullets()
        self.assertTrue(bullet.finished)
        self.assertEqual(self.target.needs.health, 72)
        self.assertEqual(self.owner.needs.health, 140)
        self.assertEqual(len(self.explosions), 1)

    def test_blast_does_not_damage_blocks_or_recheck_targets_during_rendering(self):
        block = Obstacle(250, 190, (20, 20), 'white', destructible=True)
        self.obstacles.add(block)
        self.target.x, self.target.y = 200, 200
        self.make_bullet(200, 200, explosion_radius=72)
        self.update_bullets()
        self.assertEqual(block.hits_remaining, DESTRUCTIBLE_HITS)
        self.target.x, self.target.y = 700, 200
        self.explosions.draw(pygame.Surface((WIDTH, HEIGHT)))
        self.explosions.update()
        self.assertEqual(self.target.needs.health, 80)

    def test_explosion_expiry_removes_all_sprite_memberships(self):
        with patch('pygame.time.get_ticks', return_value=1000):
            effect = Explosion(300, 300, 48)
        self.explosions.add(effect)
        drawing = pygame.sprite.Group(effect)
        with patch('pygame.time.get_ticks', return_value=1000 + EXPLOSION_LIFETIME - 1):
            self.explosions.update()
        self.assertIn(effect, drawing)
        with patch('pygame.time.get_ticks', return_value=1000 + EXPLOSION_LIFETIME):
            self.explosions.update()
        self.assertEqual(effect.groups(), [])


class ProjectileRoundTests(unittest.TestCase):
    def setUp(self):
        self.saved_scores = GameEvents.get_scores()

    def tearDown(self):
        GameEvents.player_scores.clear()
        GameEvents.player_scores.update(self.saved_scores)
        pygame.quit()

    def test_each_new_card_can_be_chosen_with_keys_and_persists_through_later_win(self):
        for upgrade_id, attribute, expected in (
            ('larger_bullets', 'bullet_radius', 5), ('heavy_bullets', 'bullet_damage', 24),
            ('ricochet', 'bullet_bounces', 1), ('explosive_rounds', 'explosion_radius', 48),
        ):
            with self.subTest(upgrade=upgrade_id):
                game = Game(seed=42, fixed_arena=True)
                game.game_events.player_died(game.player2, game.player1)
                due = game.game_events.get_game_winner_time() + game.winner_show_delay + game.winner_choose_delay
                with patch('pygame.time.get_ticks', return_value=due):
                    with patch('main.choose_upgrade_offers', return_value=[upgrade_id, 'reinforced_hull', 'rapid_fire']):
                        game.update_game()
                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
                    game.handle_events()
                    game.draw()
                with patch('pygame.time.get_ticks', return_value=due + game.upgrade_confirmation_delay):
                    game.update_game()
                self.assertEqual(getattr(game.player2, attribute), expected)
                self.assertEqual(game.upgrade_levels['Player1'][upgrade_id], 0)
                game.game_events.player_died(game.player1, game.player2)
                game.start_new_round()
                self.assertEqual(getattr(game.player2, attribute), expected)
                fresh = Game(seed=42, fixed_arena=True)
                self.assertEqual(fresh.upgrade_levels['Player2'][upgrade_id], 0)

    def test_effects_pause_in_menu_expire_during_announcement_and_reset_with_round(self):
        game = Game(seed=42, fixed_arena=True)
        with patch('pygame.time.get_ticks', return_value=1000):
            effect = Explosion(300, 300, 48)
        game.explosions.add(effect)
        game.all_sprites.add(effect)
        game.upgrade_player = 'Player2'
        with patch('pygame.time.get_ticks', return_value=1200):
            game.update_game()
        self.assertIn(effect, game.explosions)
        game.upgrade_player = None
        with patch('pygame.time.get_ticks', return_value=1200):
            game.game_events.game_winner(game.player1)
            game.update_game()
        self.assertEqual(effect.groups(), [])
        effect = Explosion(300, 300, 72)
        game.explosions.add(effect)
        game.all_sprites.add(effect)
        game.start_new_round()
        self.assertEqual(effect.groups(), [])
        self.assertEqual(len(game.explosions), 0)

    def test_bullets_cross_spikes_without_changing_player_hazard_rules(self):
        game = Game(seed=42, fixed_arena=True)
        game.game_objects(ArenaLayout([], (100, 100), (900, 600),
                                      hazards=[pygame.Rect(300, 300, 100, 32)]))
        bullet = Bullet(280, 316, 0, game.player1, bounces=1, explosion_radius=48)
        bullet.vx, bullet.vy = 150, 0
        game.bullets.add(bullet)
        game.update_game()
        self.assertFalse(bullet.finished)
        self.assertEqual(bullet.bounces_remaining, 1)
        self.assertEqual(len(game.hazards), 1)
        self.assertEqual(len(game.explosions), 0)
        self.assertTrue(game.player1.is_alive)


if __name__ == '__main__':
    unittest.main()
