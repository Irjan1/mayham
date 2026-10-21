"""Small cosmetic particles, separate from gameplay sprites and collision groups."""

from dataclasses import dataclass
import math
import random

import pygame

from config import DESTRUCTIBLE_COLOR, FPS


MAX_PARTICLES = 240


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: tuple[int, int, int]
    radius: float
    lifetime: float
    age: float = 0


class ParticleEffects:
    """Own one bounded particle list and a random stream used only for cosmetics."""

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.particles = []

    def clear(self) -> None:
        self.particles.clear()

    def add(self, position, velocity, color, radius, lifetime) -> None:
        if len(self.particles) < MAX_PARTICLES:
            self.particles.append(Particle(*position, *velocity, color, radius, lifetime))

    def exhaust(self, player) -> None:
        angle = math.radians(player.angle)
        # The nose points along (-sin, -cos); the nozzle points the other way.
        backward_x, backward_y = math.sin(angle), math.cos(angle)
        # Start just outside the nozzle of the 40x40 ship, behind its hull.
        position = (player.x + backward_x * 17, player.y + backward_y * 17)
        for _ in range(3):
            direction = angle + self.rng.uniform(-0.22, 0.22)
            speed = self.rng.uniform(60, 110)
            # Player velocity is pixels/frame; particle velocity is pixels/second.
            velocity = (player.vx * FPS + math.sin(direction) * speed,
                        player.vy * FPS + math.cos(direction) * speed)
            self.add(position, velocity, self.rng.choice(((255, 190, 65), (245, 110, 35))),
                     self.rng.uniform(2.5, 4.5), self.rng.uniform(0.18, 0.30))
        # A brief pale core makes active thrust clear without a separate flame system.
        core_position = (position[0] + backward_x * 3, position[1] + backward_y * 3)
        core_velocity = (player.vx * FPS + backward_x * 45,
                         player.vy * FPS + backward_y * 45)
        self.add(core_position, core_velocity, (255, 245, 190), 2.5, 0.06)

    def trail(self, bullet) -> None:
        color = (160, 125, 45) if bullet.explosion_radius else (145, 80, 30)
        self.add((bullet.x, bullet.y), (0, 0), color, min(2, bullet.radius * 0.35), 0.12)

    def impact(self, position, normal) -> None:
        angle = math.atan2(normal[1], normal[0])
        for _ in range(6):
            direction = angle + self.rng.uniform(-1.1, 1.1)
            speed = self.rng.uniform(35, 110)
            self.add(position, (math.cos(direction) * speed, math.sin(direction) * speed),
                     (255, 185, 85), self.rng.uniform(1, 2), self.rng.uniform(0.1, 0.22))

    def debris(self, rect) -> None:
        for _ in range(10):
            position = (self.rng.uniform(rect.left, rect.right),
                        self.rng.uniform(rect.top, rect.bottom))
            velocity = (self.rng.uniform(-65, 65), self.rng.uniform(-65, 65))
            self.add(position, velocity, DESTRUCTIBLE_COLOR,
                     self.rng.uniform(2, 3), self.rng.uniform(0.18, 0.36))

    def update(self, seconds) -> None:
        for particle in self.particles:
            particle.age += seconds
            particle.x += particle.vx * seconds
            particle.y += particle.vy * seconds
        self.particles = [particle for particle in self.particles
                          if particle.age < particle.lifetime]

    def draw(self, screen) -> None:
        for particle in self.particles:
            remaining = 1 - particle.age / particle.lifetime
            color = tuple(round(channel * remaining) for channel in particle.color)
            radius = max(1, round(particle.radius * remaining))
            pygame.draw.circle(screen, color, (round(particle.x), round(particle.y)), radius)
