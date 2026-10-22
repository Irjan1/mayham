"""
This file has the global configuration constants:

includes: screen size, gravitiy constant, starting fuel


No background as background is loaded as just black
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

PLAYER_RADIUS = 18

GRAVITY = 0.025
THRUST = 0.1

#bullet
BULLETSPEED = 8.8  # pixels per frame; a modest increase from 8.1
BULLET_RADIUS = 4
BULLET_DAMAGE = 20
BULLET_COOLDOWN = 300
EXPLOSION_RADII = (0, 48, 72)
EXPLOSION_LIFETIME = 180  # milliseconds; damage happens only at impact

WALL_DAMAGE = 0

#needs
STARTING_FUEL = 50 # after some testing low starting fuel makes the game feel more tactical
STARTING_HEALTH = 100
FUEL_COOLDOWN = 150 # having less fuel and more common fuel cans makes the players have to refuel


TITLE = "MAYHAM"
