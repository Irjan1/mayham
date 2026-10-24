"""Procedural PCM, bounded playback and audio-only gameplay event hooks."""

from array import array
from collections import defaultdict
import math
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame

import config
from main import Game
from src import audio
from src.game_events import GameEvents
from src.objects import Bullet, Fuel, Obstacle


class SynthesisTests(unittest.TestCase):
    def test_expected_effects_have_valid_deterministic_mono_and_stereo_pcm(self):
        self.assertEqual(set(audio.SOUNDS), {'engine', 'fire', 'metal_hit', 'cover_hit',
                         'rocket_hit', 'destruction', 'pickup', 'fuel_warning', 'block_break', 'upgrade'})
        state = random.getstate()
        for channels in (1, 2):
            for name, definition in audio.SOUNDS.items():
                with self.subTest(name=name, channels=channels):
                    data = audio.generate_pcm(name, channels=channels)
                    self.assertEqual(data, audio.generate_pcm(name, channels=channels))
                    samples = array('h')
                    samples.frombytes(data)
                    frames = round(audio.SAMPLE_RATE * definition['duration'])
                    self.assertEqual(len(samples), frames * channels)
                    self.assertGreater(max(map(abs, samples)), 0)
                    self.assertLessEqual(max(map(abs, samples)), round(32767 * definition['peak']))
                    if channels == 2:
                        self.assertEqual(samples[::2], samples[1::2])
                    if name != 'engine':
                        self.assertEqual((samples[0], samples[-1]), (0, 0))
                    else:
                        self.assertLess(abs(samples[0] - samples[-1]), 600)
        self.assertEqual(random.getstate(), state)

    def test_engine_loop_has_no_click_or_silence_at_the_join(self):
        for rate in (22050, 44100, 48000):
            # A non-integer pitch should also produce a continuous rumble loop.
            for frequency in (64, 63.7):
                with self.subTest(rate=rate, frequency=frequency), \
                     patch.dict(audio.SOUNDS['engine'], frequency=(frequency, frequency)):
                    samples = array('h')
                    samples.frombytes(audio.generate_pcm('engine', rate, 1))
                    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
                    steps = [b - a for a, b in zip(samples, samples[1:])]
                    step_rms = math.sqrt(sum(s * s for s in steps) / len(steps))
                    seam_step = samples[0] - samples[-1]
                    # The seam should behave like an ordinary neighbouring pair.
                    self.assertLess(abs(seam_step), 3 * step_rms)
                    self.assertLess(abs(seam_step - steps[-1]), 3 * step_rms)
                    edge_count = round(rate * 0.02)
                    edge = samples[-edge_count:] + samples[:edge_count]
                    edge_rms = math.sqrt(sum(s * s for s in edge) / len(edge))
                    self.assertGreater(edge_rms, 0.5 * rms)
                    self.assertLess(edge_rms, 1.5 * rms)

    def test_engine_is_smooth_with_a_subtle_low_rumble(self):
        for rate in (22050, 44100, 48000):
            with self.subTest(rate=rate):
                samples = array('h')
                samples.frombytes(audio.generate_pcm('engine', rate, 1))
                count = len(samples)
                rms = math.sqrt(sum(s * s for s in samples) / count)
                step_rms = math.sqrt(sum((b - a) ** 2 for a, b in zip(samples, samples[1:])) / (count - 1))
                self.assertLess(step_rms, 0.22 * rms)
                frequency = audio.SOUNDS['engine']['frequency'][0]
                # Measure the low tone: it should be audible beneath the wind,
                # without accounting for most of the signal's energy.
                sine = sum(s * math.sin(math.tau * frequency * i / rate) for i, s in enumerate(samples))
                cosine = sum(s * math.cos(math.tau * frequency * i / rate) for i, s in enumerate(samples))
                rumble_rms = math.sqrt(2) * math.hypot(sine, cosine) / count
                self.assertGreater(rumble_rms, 0.15 * rms)
                self.assertLess(rumble_rms, 0.65 * rms)

    def test_export_writes_wav_files_without_initializing_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('src.audio.Audio') as controller:
                with patch('sys.argv', ['audio', '--export', directory]):
                    audio.main()
                controller.assert_not_called()
            self.assertEqual(len(list(Path(directory).glob('*.wav'))), len(audio.SOUNDS))
            for name in audio.SOUNDS:
                with wave.open(str(Path(directory) / f'{name}.wav')) as sound:
                    self.assertEqual((sound.getnchannels(), sound.getsampwidth(), sound.getframerate()),
                                     (2, 2, audio.SAMPLE_RATE))
                    self.assertGreater(sound.getnframes(), 0)


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.controller = audio.Audio()
        self.assertTrue(self.controller.available)

    def tearDown(self):
        self.controller.close()
        pygame.quit()

    def test_mixer_format_and_cached_sound_lengths_match_buffers(self):
        for rate, channels in ((22050, 1), (44100, 2)):
            with self.subTest(rate=rate, channels=channels):
                self.controller.close()
                pygame.mixer.init(frequency=rate, size=-16, channels=channels, allowedchanges=0)
                self.controller = audio.Audio()
                self.assertEqual(self.controller.format, (rate, -16, channels))
                for name, sound in self.controller.sounds.items():
                    self.assertEqual(sound.get_raw(), audio.generate_pcm(name, rate, channels))
                    self.assertAlmostEqual(sound.get_length(), audio.SOUNDS[name]['duration'], places=3)

    def test_runtime_volumes_update_active_channels_without_synthesis(self):
        sounds = self.controller.sounds.copy()
        self.controller.set_engine('one', True)
        with patch.object(config, 'AUDIO_MASTER_VOLUME', 0.4), \
             patch.object(config, 'AUDIO_ENGINE_VOLUME', 0.5), \
             patch.object(config, 'AUDIO_WEAPONS_VOLUME', 0.25), \
             patch.object(config, 'AUDIO_IMPACTS_VOLUME', 0.75), \
             patch.object(config, 'AUDIO_PICKUP_UI_VOLUME', 1.0):
            with patch('src.audio.generate_pcm', side_effect=AssertionError('Must reuse buffers')):
                self.controller.apply_settings()
            for category, expected in (('weapons', 0.1), ('impacts', 0.3), ('pickup_ui', 0.4)):
                for index in audio.CHANNEL_POOLS[category]:
                    self.assertAlmostEqual(self.controller.channels[index].get_volume(), expected, delta=0.01)
            with patch('pygame.time.get_ticks', return_value=1000):
                self.controller.play('fire', source='one')
                self.controller.play('fire', source='two')
            for index in audio.CHANNEL_POOLS['weapons'][:2]:
                self.assertAlmostEqual(self.controller.channels[index].get_volume(), 0.1, delta=0.01)
        self.assertEqual(self.controller.sounds, sounds)
        self.assertAlmostEqual(sounds['engine'].get_volume(), 0.2, delta=0.01)
        self.assertTrue(all(sound.get_volume() == 1 for name, sound in sounds.items() if name != 'engine'))

    def test_engine_volume_change_survives_an_in_progress_native_fade(self):
        self.controller.set_engine('one', True)
        with patch.object(config, 'AUDIO_MASTER_VOLUME', 0.8), \
             patch.object(config, 'AUDIO_ENGINE_VOLUME', 0.5):
            self.controller.apply_settings()
            # Let the dummy mixer's native fade complete; no speakers are needed.
            pygame.time.wait(audio.ENGINE_FADE_IN_MS + 60)
            channel = self.controller.engine_channels['one']
            effective = channel.get_volume() * self.controller.sounds['engine'].get_volume()
            self.assertAlmostEqual(effective, 0.4, delta=0.01)
            self.assertTrue(channel.get_busy())

    def test_mute_stops_loops_and_unmute_can_restart_them(self):
        self.controller.set_engine('one', True)
        with patch.object(config, 'AUDIO_ENABLED', False):
            self.controller.apply_settings()
            self.assertFalse(self.controller.active_engines)
            self.assertFalse(any(channel.get_busy() for channel in self.controller.channels))
            self.assertFalse(self.controller.play('fire'))
            self.controller.set_engine('one', True)
            self.assertFalse(self.controller.active_engines)
        self.controller.apply_settings()
        self.controller.set_engine('one', True)
        self.assertIn('one', self.controller.active_engines)

    def test_engine_channels_are_independent_and_do_not_restart_each_frame(self):
        self.controller.set_engine('one', True)
        self.controller.set_engine('two', True)
        first = Mock(wraps=self.controller.engine_channels['one'])
        second = self.controller.engine_channels['two']
        self.controller.engine_channels['one'] = first
        for _ in range(100):
            self.controller.set_engine('one', True)
        first.play.assert_not_called()
        self.controller.set_engine('one', False)
        first.fadeout.assert_called_once_with(audio.ENGINE_FADE_OUT_MS)
        self.assertNotIn('one', self.controller.active_engines)
        self.assertIn('two', self.controller.active_engines)
        first.stop()
        self.assertTrue(second.get_busy())
        self.assertIs(second.get_sound(), self.controller.sounds['engine'])

    def test_cooldowns_are_per_player_and_channel_pools_stay_bounded(self):
        self.controller.set_engine('one', True)
        self.controller.set_engine('two', True)
        with patch('pygame.time.get_ticks', return_value=1000):
            self.assertTrue(self.controller.play('fire', source='one'))
            self.assertFalse(self.controller.play('fire', source='one'))
            self.assertTrue(self.controller.play('fire', source='two'))
        for now in range(1020, 3020, 20):
            with patch('pygame.time.get_ticks', return_value=now):
                self.controller.play('fire', source='one')
            busy = sum(self.controller.channels[index].get_busy() for index in audio.CHANNEL_POOLS['weapons'])
            self.assertLessEqual(busy, 3)
        self.assertEqual(len(self.controller.active_engines), 2)
        self.assertTrue(self.controller.play('pickup'))
        self.assertEqual(pygame.mixer.get_num_channels(), audio.CHANNEL_COUNT)

    def test_crowded_minor_effects_drop_but_destruction_can_replace_an_effect(self):
        for index in audio.CHANNEL_POOLS['impacts']:
            self.controller.channels[index].play(self.controller.sounds['engine'], loops=-1)
        self.assertFalse(self.controller.play('metal_hit'))
        self.assertTrue(self.controller.play('destruction'))
        self.assertIs(self.controller.channels[audio.CHANNEL_POOLS['impacts'][0]].get_sound(),
                      self.controller.sounds['destruction'])

    def test_round_reset_and_close_release_playback_and_allow_new_engines(self):
        self.controller.set_engine('old player', True)
        self.controller.play('fire')
        self.controller.reset_round()
        self.assertFalse(self.controller.engine_channels)
        self.assertFalse(self.controller.last_played)
        self.assertFalse(any(channel.get_busy() for channel in self.controller.channels))
        self.controller.set_engine('new player', True)
        self.assertIn('new player', self.controller.active_engines)
        self.controller.close()
        self.assertIsNone(pygame.mixer.get_init())
        self.assertFalse(self.controller.play('fire'))

    def test_disabled_start_skips_synthesis_and_can_be_enabled_later(self):
        self.controller.close()
        with patch.object(config, 'AUDIO_ENABLED', False):
            with patch('src.audio._sound_buffers') as generate:
                self.controller = audio.Audio()
            generate.assert_not_called()
            self.assertFalse(self.controller.available)
        self.controller.apply_settings()
        self.assertTrue(self.controller.available)

    def test_missing_device_disables_playback_and_reports_failure_only_once(self):
        self.controller.close()
        with patch('pygame.mixer.init', side_effect=pygame.error('No audio device')):
            with patch('src.audio._failure_reported', False), patch('builtins.print') as report:
                first, second = audio.Audio(), audio.Audio()
                self.assertFalse(first.available)
                self.assertFalse(second.available)
                self.assertFalse(first.play('fire'))
                first.set_engine('one', True)
                first.close()
                second.close()
                report.assert_called_once()

    def test_programming_errors_are_not_swallowed_even_when_muted(self):
        with self.assertRaises(KeyError):
            self.controller.play('misspelled_sound')
        with patch.object(config, 'AUDIO_ENABLED', False):
            self.controller.apply_settings()
            with self.assertRaises(KeyError):
                self.controller.play('misspelled_sound')
        self.controller.close()
        with patch('src.audio._sound_buffers', side_effect=ValueError('Bad synthesis definition')):
            with self.assertRaisesRegex(ValueError, 'Bad synthesis'):
                audio.Audio()


class AudioEventTests(unittest.TestCase):
    def setUp(self):
        self.saved_scores = GameEvents.get_scores()
        self.requests = Mock(spec=audio.Audio)
        with patch('main.Audio', return_value=self.requests):
            self.game = Game(seed=42, fixed_arena=True)
        self.requests.reset_mock()

    def tearDown(self):
        GameEvents.player_scores.update(self.saved_scores)
        pygame.quit()

    def test_shots_request_audio_only_when_a_projectile_is_created(self):
        with patch('pygame.time.get_ticks', return_value=1000):
            self.game.player1.shoot(self.game.bullets)
            self.game.player1.shoot(self.game.bullets)
        self.assertEqual(len(self.game.bullets), 1)
        self.requests.play.assert_called_once_with('fire', source=self.game.player1)
        self.assertIs(next(iter(self.game.bullets)).audio, self.requests)

    def test_engine_requests_follow_real_thrust_fuel_and_release(self):
        player = self.game.player1
        keys = defaultdict(bool, {player.controls['up']: True})
        player.needs.fuel = 2
        with patch('pygame.time.get_ticks', return_value=1000):
            player.handle_input(keys, self.game.bullets)
        self.requests.set_engine.assert_called_with(player, True)
        with patch('pygame.time.get_ticks', return_value=2000):
            player.handle_input(keys, self.game.bullets)
        self.assertEqual(player.needs.fuel, 0)
        self.requests.set_engine.assert_called_with(player, False)
        player.needs.fuel = 2
        player.handle_input(defaultdict(bool), self.game.bullets)
        self.requests.set_engine.assert_called_with(player, False)

    def test_projectile_contacts_choose_material_sound_and_cover_breaks_on_third_hit(self):
        for destructible, sound in ((False, 'metal_hit'), (True, 'cover_hit')):
            self.requests.reset_mock()
            block = Obstacle(300, 200, (80, 80), 'white', destructible=destructible, audio=self.requests)
            bullet = Bullet(290, 240, 0, self.game.player1, bounces=1, audio=self.requests)
            bullet.vx, bullet.vy = 2, 0
            bullet.bounce((-1, 0), 1, block)
            self.requests.play.assert_called_once_with(sound)
            if destructible:
                group = pygame.sprite.Group(block)
                block.take_bullet_hit()
                self.assertIn(block, group)
                block.take_bullet_hit()
                self.assertNotIn(block, group)
                self.requests.play.assert_called_with('block_break')

    def test_wall_damage_uses_existing_cooldown_and_death_stops_engines(self):
        player = self.game.player1
        with patch('src.game_events.WALL_DAMAGE', 7):
            with patch('pygame.time.get_ticks', return_value=1000):
                player.take_wall_or_obstacle_damage(self.game.players, self.game.game_events)
                player.take_wall_or_obstacle_damage(self.game.players, self.game.game_events)
        self.assertEqual(player.needs.health, config.STARTING_HEALTH - 7)
        self.requests.play.assert_called_once_with('rocket_hit', source=player)
        self.requests.reset_mock()
        self.game.game_events.damage_player(player, 1000, self.game.player2)
        self.requests.play.assert_called_once_with('destruction', source=player)
        self.requests.stop_engines.assert_called_once()
        self.game.game_events.damage_player(player, 1000, self.game.player2)
        self.assertEqual(self.requests.play.call_count, 1)
        self.game.start_new_round()
        self.requests.reset_round.assert_called_once()

    def test_fuel_warning_is_one_event_and_pickup_occurs_only_on_collection(self):
        deadline = self.game.fuel_spawn_at
        self.game.update_fuel(deadline - config.FUEL_WARNING_DURATION)
        for offset in (10, 100, 300):
            self.game.update_fuel(deadline - config.FUEL_WARNING_DURATION + offset)
            self.game.draw()
        self.requests.play.assert_called_once_with('fuel_warning')
        self.game.update_fuel(deadline)
        can = next(iter(self.game.fuel_cans))
        player = self.game.player1
        player.x, player.y = can.rect.center
        player.update_rect()
        player.pick_up_fuel(self.game.fuel_cans)
        player.pick_up_fuel(self.game.fuel_cans)
        self.requests.play.assert_called_with('pickup', source=player)
        self.assertEqual(self.requests.play.call_count, 2)

    def test_upgrade_confirmation_plays_once_for_an_accepted_choice(self):
        self.game.upgrade_player = 'Player2'
        self.game.upgrade_choices = ['rapid_fire']
        self.game.select_upgrade(0)
        self.game.select_upgrade(0)
        self.requests.play.assert_called_once_with('upgrade')


class AudioGameplayTests(unittest.TestCase):
    def tearDown(self):
        pygame.quit()

    def test_initialization_failure_does_not_prevent_gameplay(self):
        with patch('pygame.mixer.get_init', return_value=None), \
             patch('pygame.mixer.init', side_effect=pygame.error('No device')), \
             patch('src.audio._failure_reported', True):
            game = Game(seed=42, fixed_arena=True)
            self.assertFalse(game.audio.available)
            game.update_game()
            game.draw()
            self.assertEqual(len(game.players), 2)
            game.audio.close()

    def test_gameplay_and_random_streams_match_with_audio_enabled_or_disabled(self):
        state = random.getstate()
        def play(enabled):
            with patch.object(config, 'AUDIO_ENABLED', enabled):
                with patch('pygame.time.get_ticks', return_value=1000):
                    game = Game(seed=42, fixed_arena=True)
                keys = defaultdict(bool, {game.player1.controls['up']: True,
                                         game.player1.controls['shoot']: True,
                                         game.player2.controls['up']: True})
                for frame in range(20):
                    with patch('pygame.time.get_ticks', return_value=1000 + frame * 200), \
                         patch('pygame.key.get_pressed', return_value=keys):
                        game.update_game()
                snapshot = (game.arena, [(p.x, p.y, p.vx, p.vy, p.needs.fuel, p.needs.health)
                                         for p in game.players],
                            [(b.x, b.y, b.vx, b.vy, b.damage) for b in game.bullets],
                            game.fuel_state, game.fuel_spawn_position, game.fuel_spawn_at,
                            game.fuel_rng.getstate(), game.style_rng.getstate(), game.upgrade_rng.getstate())
                game.audio.close()
                return snapshot
        self.assertEqual(play(True), play(False))
        self.assertEqual(random.getstate(), state)


if __name__ == '__main__':
    unittest.main()
