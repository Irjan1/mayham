"""Keyboard navigation and the handoff to the existing game loop."""

import os
import unittest
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame

import main
from config import HEIGHT, WIDTH
from src.game_events import GameEvents
from src.menu import MainMenu, MENU_OPTIONS


def keypress(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key)


class MenuTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.menu = MainMenu((WIDTH, HEIGHT), seed=42)

    def tearDown(self):
        pygame.quit()

    def test_arrows_wrap_and_enter_selects_multiplayer(self):
        self.menu.handle_event(keypress(pygame.K_UP))
        self.assertEqual(self.menu.selected_index, len(MENU_OPTIONS) - 1)
        self.menu.handle_event(keypress(pygame.K_DOWN))
        self.assertEqual(self.menu.selected_index, 0)
        self.assertEqual(self.menu.handle_event(keypress(pygame.K_RETURN)), 'multiplayer')

    def test_controls_screen_returns_to_same_menu_selection(self):
        self.menu.handle_event(keypress(pygame.K_DOWN))
        self.assertIsNone(self.menu.handle_event(keypress(pygame.K_RETURN)))
        self.assertEqual(self.menu.screen_name, 'controls')
        self.assertIsNone(self.menu.handle_event(keypress(pygame.K_RETURN)))
        self.menu.handle_event(keypress(pygame.K_UP))
        self.assertEqual(self.menu.selected_index, 1)
        self.menu.handle_event(keypress(pygame.K_ESCAPE))
        self.assertEqual(self.menu.screen_name, 'main')
        self.assertEqual(self.menu.selected_index, 1)

    def test_quit_option_and_window_close(self):
        self.menu.handle_event(keypress(pygame.K_UP))
        self.assertEqual(self.menu.handle_event(keypress(pygame.K_RETURN)), 'quit')
        self.menu.screen_name = 'controls'
        self.assertEqual(self.menu.handle_event(pygame.event.Event(pygame.QUIT)), 'quit')

    def test_help_uses_actual_key_bindings(self):
        self.assertEqual(self.menu.control_rows, [
            ('Rotate left', 'Left Arrow', 'A'),
            ('Rotate right', 'Right Arrow', 'D'),
            ('Thrust', 'Up Arrow', 'W'),
            ('Shoot', 'Right Shift', 'Space'),
        ])

    def test_screens_reuse_cached_background(self):
        cached = self.menu.background
        screen = pygame.Surface((WIDTH, HEIGHT))
        with patch('src.menu.generate_background') as generate:
            for screen_name in ('main', 'controls', 'main'):
                self.menu.screen_name = screen_name
                self.menu.draw(screen)
            generate.assert_not_called()
        self.assertIs(self.menu.background, cached)


class ApplicationStartupTests(unittest.TestCase):
    def setUp(self):
        self.saved_scores = GameEvents.get_scores()

    def tearDown(self):
        GameEvents.player_scores.update(self.saved_scores)
        pygame.quit()

    def test_menu_launches_one_fresh_match_with_original_options(self):
        for fixed in (False, True):
            with self.subTest(fixed=fixed):
                GameEvents.player_scores.update(Player1=5, Player2=7)
                events = [[], [keypress(pygame.K_DOWN), keypress(pygame.K_RETURN)],
                          [keypress(pygame.K_ESCAPE), keypress(pygame.K_UP),
                           keypress(pygame.K_RETURN), keypress(pygame.K_RETURN)]]
                with patch('pygame.event.get', side_effect=events):
                    with patch.object(main.Game, 'run', autospec=True) as run:
                        with patch('main.Game', wraps=main.Game) as create_game:
                            main.run_application(seed=0, fixed_arena=fixed, style='corridors')
                create_game.assert_called_once_with(seed=0, fixed_arena=fixed, style='corridors')
                run.assert_called_once()
                game = run.call_args.args[0]
                self.assertEqual(game.arena_seed, 0)
                self.assertEqual(game.arena.style, 'fixed' if fixed else 'corridors')
                self.assertEqual(GameEvents.get_scores(), {'Player1': 0, 'Player2': 0})
                self.assertTrue(all(level == 0 for levels in game.upgrade_levels.values()
                                    for level in levels.values()))
                game.start_new_round()
                self.assertEqual(game.arena_seed, 1)

    def test_quitting_menu_does_not_construct_game_or_reset_scores(self):
        GameEvents.player_scores.update(Player1=5, Player2=7)
        with patch('pygame.event.get', return_value=[pygame.event.Event(pygame.QUIT)]):
            with patch('main.Game') as create_game:
                main.run_application(seed=42)
        create_game.assert_not_called()
        self.assertEqual(GameEvents.get_scores(), {'Player1': 5, 'Player2': 7})
        self.assertFalse(pygame.get_init())

    def test_command_line_options_are_forwarded(self):
        with patch('sys.argv', ['main.py', '--seed', '42', '--fixed-arena', '--style', 'scattered']):
            with patch('main.run_application') as application:
                main.main()
        application.assert_called_once_with(seed=42, fixed_arena=True, style='scattered')

    def test_direct_game_construction_bypasses_menu_and_loop(self):
        with patch('main.MainMenu') as menu:
            with patch.object(main.Game, 'run') as run:
                game = main.Game(seed=42)
        menu.assert_not_called()
        run.assert_not_called()
        self.assertEqual(len(game.players), 2)


if __name__ == '__main__':
    unittest.main()
