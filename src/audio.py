"""Procedural sound effects, mixer ownership and optional listening previews.

Sound timbres and channel limits live here. User volume/mute settings live in
config.py. Nothing is initialized or synthesized merely by importing this module.
"""

import argparse
from array import array
from functools import lru_cache
import math
from pathlib import Path
import random
import sys
import wave

import pygame # type: ignore

import config


SAMPLE_RATE = 22050
MIXER_BUFFER = 512
ENGINE_FADE_IN_MS = 60
ENGINE_FADE_OUT_MS = 100
ATTACK_SECONDS = 0.004
RELEASE_SECONDS = 0.012
NOISE_SMOOTHING = 0.14
# Engine timbre only; the existing volume settings and channel fades stay separate.
ENGINE_WIND_CUTOFF_HZ = 700
ENGINE_RUMBLE_HARMONIC = 0.12
ENGINE_WIND_SWELL = 0.10

# Small, separate pools keep shooting from stealing engines or pickup/UI cues.
CHANNEL_POOLS = {'engines': (0, 1), 'weapons': (2, 3, 4),
                 'impacts': (5, 6, 7), 'pickup_ui': (8, 9)}
CHANNEL_COUNT = 10
IMPORTANT_SOUNDS = {'destruction', 'pickup', 'upgrade'}

# peak leaves PCM headroom; cooldown is audio-only, in milliseconds.
SOUNDS = {
    'engine': dict(category='engines', duration=2.0, frequency=(64, 64),
                   waveform='engine', noise=0.92, peak=0.14, cooldown=0),
    'fire': dict(category='weapons', duration=0.11, frequency=(1100, 180),
                 waveform='triangle', noise=0.12, peak=0.22, cooldown=20),
    'metal_hit': dict(category='impacts', duration=0.09, frequency=(1700, 1100),
                      waveform='metal', noise=0.18, peak=0.17, cooldown=35),
    'cover_hit': dict(category='impacts', duration=0.11, frequency=(250, 80),
                      waveform='rumble', noise=0.65, peak=0.18, cooldown=35),
    'rocket_hit': dict(category='impacts', duration=0.22, frequency=(170, 45),
                       waveform='rumble', noise=0.70, peak=0.26, cooldown=150),
    'destruction': dict(category='impacts', duration=0.48, frequency=(105, 35),
                        waveform='rumble', noise=0.85, peak=0.30, cooldown=200),
    'pickup': dict(category='pickup_ui', duration=0.22, frequency=(550, 1250),
                   waveform='chime', noise=0.02, peak=0.23, cooldown=80),
    'fuel_warning': dict(category='pickup_ui', duration=0.18, frequency=(380, 640),
                         waveform='chime', noise=0.03, peak=0.12, cooldown=300),
    'block_break': dict(category='impacts', duration=0.25, frequency=(360, 75),
                        waveform='metal', noise=0.78, peak=0.24, cooldown=70),
    'upgrade': dict(category='pickup_ui', duration=0.27, frequency=(660, 1100),
                    notes=(660, 880, 1100), waveform='chime', noise=0.01,
                    peak=0.18, cooldown=150),
}
_failure_reported = False


def _waveform(phase, kind):
    angle = math.tau * phase
    fundamental = math.sin(angle)
    if kind == 'triangle':
        return 1 - 4 * abs(phase % 1 - 0.5)
    if kind == 'metal':
        return (fundamental + 0.5 * math.sin(angle * 2.71) +
                0.25 * math.sin(angle * 4.13)) / 1.75
    if kind == 'chime':
        return (fundamental + 0.35 * math.sin(angle * 1.5)) / 1.35
    if kind == 'rumble':
        return (fundamental + 0.3 * math.sin(angle * 0.5)) / 1.3
    raise ValueError(f'Unknown audio waveform: {kind}')


def _engine_samples(count, sample_rate, rng):
    """Blend soft, looping wind with a quiet mechanical rumble."""
    definition = SOUNDS['engine']
    white_noise = [rng.uniform(-1, 1) for _ in range(count)]
    smoothing = 1 - math.exp(-math.tau * ENGINE_WIND_CUTOFF_HZ / sample_rate)
    first_filter = second_filter = 0.0
    # Two low-pass filters remove sharp hiss. Run the same loop once to settle
    # their state, then keep the second pass so the join needs no fade or dip.
    for _ in range(2):
        wind = []
        for sample in white_noise:
            first_filter += smoothing * (sample - first_filter)
            second_filter += smoothing * (first_filter - second_filter)
            wind.append(second_filter)

    # Whole cycles keep the rumble continuous even when its pitch is adjusted.
    cycles = round(definition['frequency'][0] * count / sample_rate)
    blend = definition['noise']
    samples = []
    for index, noise in enumerate(wind):
        angle = math.tau * cycles * index / count
        rumble = (math.sin(angle) + ENGINE_RUMBLE_HARMONIC * math.sin(2 * angle))
        rumble /= 1 + ENGINE_RUMBLE_HARMONIC
        # One gentle swell per loop adds movement without a fast electronic pulse.
        swell = 1 - ENGINE_WIND_SWELL + ENGINE_WIND_SWELL * math.cos(math.tau * index / count)
        samples.append((1 - blend) * rumble + blend * noise * swell)
    return samples


def generate_pcm(name, sample_rate=SAMPLE_RATE, channels=2):
    """Return native signed-16 PCM, interleaved for a mono or stereo mixer."""
    definition = SOUNDS[name]
    if sample_rate <= 0 or channels not in (1, 2):
        raise ValueError('Audio requires a positive sample rate and mono/stereo output')
    count = max(2, round(sample_rate * definition['duration']))
    rng = random.Random(f'mayham-audio:{name}')
    if name == 'engine':
        samples = _engine_samples(count, sample_rate, rng)
    else:
        phase = 0.0
        filtered_noise = 0.0
        samples = []
        for index in range(count):
            progress = index / (count - 1)
            start, end = definition['frequency']
            frequency = start + (end - start) * progress
            if 'notes' in definition:
                notes = definition['notes']
                frequency = notes[min(len(notes) - 1, int(progress * len(notes)))]
            tone = _waveform(phase, definition['waveform'])
            phase += frequency / sample_rate
            white_noise = rng.uniform(-1, 1)
            filtered_noise += NOISE_SMOOTHING * (white_noise - filtered_noise)
            noise = 0.7 * filtered_noise + 0.3 * white_noise
            attack = min(1, index / (sample_rate * ATTACK_SECONDS))
            release = min(1, (count - 1 - index) / (sample_rate * RELEASE_SECONDS))
            envelope = attack * release * math.exp(-4 * progress)
            blend = definition['noise']
            samples.append(((1 - blend) * tone + blend * noise) * envelope)
    # Normalize after layering so no individual buffer can clip.
    scale = 32767 * definition['peak'] / max(max(map(abs, samples)), 1e-9)
    pcm = array('h')
    for sample in samples:
        value = round(sample * scale)
        pcm.extend([value] * channels)
    return pcm.tobytes()


@lru_cache(maxsize=2)
def _sound_buffers(sample_rate, channels):
    """Reuse synthesis across matches and mixer reinitialization at the same format."""
    return {name: generate_pcm(name, sample_rate, channels) for name in SOUNDS}


class Audio:
    """One controller owns ten channels; gameplay only requests events or engine state."""

    def __init__(self):
        self.available = False
        self.enabled = False
        self.format = None
        self.sounds = {}
        self.channels = []
        self.engine_channels = {}
        self.active_engines = set()
        self.last_played = {}
        self.channel_started = [0] * CHANNEL_COUNT
        self.volumes = {}
        self.apply_settings()

    def _initialize(self):
        global _failure_reported
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2,
                                  buffer=MIXER_BUFFER, allowedchanges=0)
            self.format = pygame.mixer.get_init()
            rate, sample_format, channels = self.format
            if sample_format != -16 or channels not in (1, 2):
                raise pygame.error('Audio requires a signed-16 mono/stereo mixer')
            buffers = _sound_buffers(rate, channels)
            self.sounds = {name: pygame.mixer.Sound(buffer=data) for name, data in buffers.items()}
            pygame.mixer.set_num_channels(CHANNEL_COUNT)
            pygame.mixer.set_reserved(len(CHANNEL_POOLS['engines']))
            self.channels = [pygame.mixer.Channel(index) for index in range(CHANNEL_COUNT)]
            self.available = True
        except pygame.error as error:
            self.available = False
            self.enabled = False
            if not _failure_reported:
                print(f'Audio unavailable; continuing silently: {error}')
                _failure_reported = True

    def apply_settings(self):
        """Re-read config after a future Settings menu changes volume or mute."""
        self.enabled = bool(config.AUDIO_ENABLED)
        if self.enabled and (not self.available or pygame.mixer.get_init() != self.format):
            self._initialize()
        master = max(0.0, min(1.0, config.AUDIO_MASTER_VOLUME))
        levels = {'engines': config.AUDIO_ENGINE_VOLUME, 'weapons': config.AUDIO_WEAPONS_VOLUME,
                  'impacts': config.AUDIO_IMPACTS_VOLUME, 'pickup_ui': config.AUDIO_PICKUP_UI_VOLUME}
        self.volumes = {category: master * max(0.0, min(1.0, level))
                        for category, level in levels.items()}
        if not self.available or pygame.mixer.get_init() != self.format:
            return
        if not self.enabled:
            self.reset_round()
        # SDL restores a channel's old volume when its fade finishes. Keep engine
        # gain on the shared Sound, independently of each player's channel fade.
        self.sounds['engine'].set_volume(self.volumes['engines'])
        for category, indices in CHANNEL_POOLS.items():
            if category != 'engines':
                for index in indices:
                    self.channels[index].set_volume(self.volumes[category])

    def _can_play(self):
        return self.enabled and self.available and pygame.mixer.get_init() == self.format

    def play(self, name, source=None):
        definition = SOUNDS[name]  # Misspelled events are programming errors, even when muted.
        if name == 'engine':
            raise ValueError('Use set_engine for engine loops')
        if not self._can_play():
            return False
        now = pygame.time.get_ticks()
        key = (name, source)
        previous = self.last_played.get(key)
        if previous is not None and now - previous < definition['cooldown']:
            return False
        pool = CHANNEL_POOLS[definition['category']]
        index = next((index for index in pool if not self.channels[index].get_busy()), None)
        if index is None:
            if name not in IMPORTANT_SOUNDS:
                return False  # Drop crowded minor effects; never queue a growing backlog.
            index = min(pool, key=lambda index: self.channel_started[index])
        self.channels[index].play(self.sounds[name])
        self.channels[index].set_volume(self.volumes[definition['category']])
        self.channel_started[index] = now
        self.last_played[key] = now
        return True

    def set_engine(self, player, active):
        if not self._can_play():
            return
        if player not in self.engine_channels:
            if not active or len(self.engine_channels) == len(CHANNEL_POOLS['engines']):
                return
            index = CHANNEL_POOLS['engines'][len(self.engine_channels)]
            self.engine_channels[player] = self.channels[index]
        channel = self.engine_channels[player]
        if active and player not in self.active_engines:
            channel.set_volume(1.0)
            channel.play(self.sounds['engine'], loops=-1, fade_ms=ENGINE_FADE_IN_MS)
            self.active_engines.add(player)
        elif not active and player in self.active_engines:
            channel.fadeout(ENGINE_FADE_OUT_MS)
            self.active_engines.remove(player)

    def stop_engines(self):
        if self.available and pygame.mixer.get_init() == self.format:
            for channel in self.engine_channels.values():
                channel.fadeout(ENGINE_FADE_OUT_MS)
        self.active_engines.clear()

    def reset_round(self):
        if self.available and pygame.mixer.get_init() == self.format:
            for channel in self.channels:
                channel.stop()
        self.engine_channels.clear()
        self.active_engines.clear()
        self.last_played.clear()
        self.channel_started = [0] * CHANNEL_COUNT

    def close(self):
        self.reset_round()
        if self.available and pygame.mixer.get_init() == self.format:
            pygame.mixer.quit()
        self.available = False
        self.enabled = False


def export_sounds(directory):
    """Write optional WAV previews; normal gameplay keeps all audio in memory."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in _sound_buffers(SAMPLE_RATE, 2).items():
        samples = array('h')
        samples.frombytes(data)
        if sys.byteorder != 'little':
            samples.byteswap()  # WAV uses little endian; the mixer uses native signed-16.
        with wave.open(str(directory / f'{name}.wav'), 'wb') as output:
            output.setparams((2, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
            output.writeframes(samples.tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true', help='Play each sound once')
    parser.add_argument('--sound', choices=SOUNDS, help='Preview one sound')
    parser.add_argument('--export', type=Path, help='Save optional WAV previews to a directory')
    args = parser.parse_args()
    if args.sound and not args.preview:
        parser.error('--sound requires --preview')
    if args.export:
        export_sounds(args.export)
        print(f'Saved WAV previews to {args.export}')
    if not args.preview:
        if not args.export:
            parser.print_help()
        return
    audio = Audio()
    try:
        if not audio._can_play():
            print('Audio preview is disabled or unavailable.')
            return
        for name in [args.sound] if args.sound else SOUNDS:
            print(f'Playing {name}')
            if name == 'engine':
                audio.set_engine('preview', True)
                pygame.time.wait(1200)
                audio.set_engine('preview', False)
                pygame.time.wait(ENGINE_FADE_OUT_MS + 100)
            else:
                audio.play(name)
                pygame.time.wait(round(SOUNDS[name]['duration'] * 1000) + 200)
    finally:
        audio.close()


if __name__ == '__main__':
    main()
