"""
This file has the global configuration constants:

includes: screen size, gravitiy constant, starting fuel, bullet speed,
audio, obstacle settings

Authors: Irjan Evertsen and Emil Olsen-Kristiansen
"""


WIDTH = 1080
HEIGHT = 720
FPS = 60

OBSTACLE_SIZE = (160, 160)
OBSTACLE_COLOR = (255, 255, 255)
DESTRUCTIBLE_COLOR = (205, 160, 80)
DESTRUCTIBLE_HITS = 3
HAZARD_COLOR = (255, 75, 85)

FUEL_COLOR = (255, 140, 0)
FUEL_SIZE = (30, 30)
FUEL_RESPAWN_DELAY = 10000  # milliseconds, from collection (also the first spawn delay)
FUEL_WARNING_DURATION = 7000  # clamped to the respawn delay
FUEL_WARNING_PULSE_HZ = 1.0
FUEL_WARNING_MIN_ALPHA = 65
FUEL_WARNING_MAX_ALPHA = 175

PLAYER_RADIUS = 18

GRAVITY = 0.020
THRUST = 0.1

#bullet
BULLETSPEED = 8.8  # pixels per frame; a modest increase from 8.1
BULLET_RADIUS = 4
BULLET_DAMAGE = 35
BULLET_COOLDOWN = 600
EXPLOSION_RADII = (0, 48, 72)
EXPLOSION_LIFETIME = 180  # milliseconds; damage happens only at impact

WALL_DAMAGE = 5

#needs
STARTING_FUEL = 50 # after some testing low starting fuel makes the game feel more tactical
STARTING_HEALTH = 100
FUEL_COOLDOWN = 150 # having less fuel and more common fuel cans makes the players have to refuel


TITLE = "MAYHAM"

# Audio volumes (0.0–1.0). Call game.audio.apply_settings() after runtime changes.
AUDIO_ENABLED = True
AUDIO_MASTER_VOLUME = 0.55
AUDIO_ENGINE_VOLUME = 0.35
AUDIO_WEAPONS_VOLUME = 0.40
AUDIO_IMPACTS_VOLUME = 0.10
AUDIO_PICKUP_UI_VOLUME = 0.70
