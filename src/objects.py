"""
Object file for the game

Contains shared visible game objects:
obstacle, bullets, fuel

Also contains the base Ship Class

All objects inherit from pygame.sprite.Sprite so they later can be stored
in pygame.sprite.Group objects. This enables Group.update and Group.draw later


Authors: Irjan Evertsen and Emil Olsen-Kristiansen
"""

import pygame
import math
from config import WIDTH, HEIGHT, BULLETSPEED, DESTRUCTIBLE_COLOR, DESTRUCTIBLE_HITS, HAZARD_COLOR

class Obstacle(pygame.sprite.Sprite):
    """A static rectangular obstacle that ships can collide with."""

    def __init__(self, x: int, y: int, size: tuple[int, int], color: tuple[int, int, int],
                 destructible: bool = False):
        """Crate the obstacle at the given position with given size and color"""
        super().__init__()

        self.destructible = destructible
        self.hits_remaining = DESTRUCTIBLE_HITS if destructible else 0
        self.image = pygame.Surface(size)
        self.image.fill(DESTRUCTIBLE_COLOR if destructible else color)
        self.rect = self.image.get_rect(topleft=(x, y))

    def take_bullet_hit(self) -> None:
        """Three hits break a tan block; white obstacles remain permanent."""
        if not self.destructible:
            return
        self.hits_remaining -= 1
        if self.hits_remaining <= 0:
            self.kill()
            return
        width, height = self.image.get_size()
        # Cracks accumulate, making the remaining durability visible.
        for crack in range(DESTRUCTIBLE_HITS - self.hits_remaining):
            x = width * (crack + 1) // DESTRUCTIBLE_HITS
            pygame.draw.line(self.image, "black", (x, 0), (width // 2, height), 3)


def draw_hazard(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw the same red spike warning in gameplay and arena previews."""
    pygame.draw.rect(surface, (90, 15, 25), rect)
    for x in range(rect.left, rect.right, 16):
        pygame.draw.polygon(surface, HAZARD_COLOR, [
            (x, rect.bottom - 1), (min(x + 8, rect.right - 1), rect.top),
            (min(x + 16, rect.right - 1), rect.bottom - 1),
        ])
    pygame.draw.rect(surface, HAZARD_COLOR, rect, 2)


class Hazard(pygame.sprite.Sprite):
    """A visible rectangular spike zone; contact kills a player."""

    def __init__(self, rect: pygame.Rect):
        super().__init__()
        self.rect = rect.copy()
        self.image = pygame.Surface(rect.size)
        draw_hazard(self.image, self.image.get_rect())


class Bullet(pygame.sprite.Sprite):
    """
    The bullet class for the game
    Initializes the bullet and updates it
    Has collision vs other player, obstacles, and borders
    """

    def __init__(self, x: float, y: float, angle: float, owner: pygame.sprite.Sprite, radius: int = 4):
        """Create bullet at given position and angle"""
        super().__init__()
        

        self.x = x
        self.y = y
        self.angle = angle
        self.owner = owner
        self.speed = BULLETSPEED
        self.radius = radius

        self.image = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, "orange", (self.radius, self.radius), self.radius)

        self.rect = self.image.get_rect(center=(round(self.x), round(self.y)))

        radians = math.radians(self.angle)
        self.vx = -math.sin(radians) * self.speed
        self.vy = -math.cos(radians) * self.speed

    def update(self, players, obstacles: pygame.sprite.Group, game_events) -> None:
        """Handles bullet movment and collision with obstacles and the player"""
        self.x += self.vx
        self.y += self.vy

        self.rect.center = (round(self.x), round(self.y))


        # collision
        for player in players:
            if player != self.owner and pygame.sprite.collide_circle(self, player):
                game_events.bullet_hit_player(self, player)  # reduserer needs.health
                return

        ## outside boundaries
        if self.rect.right < 0 or self.rect.left > WIDTH:
            self.kill()

        if self.rect.bottom < 0 or self.rect.top > HEIGHT:
            self.kill()

        obstacle = pygame.sprite.spritecollideany(self, obstacles)
        if obstacle is not None:
            obstacle.take_bullet_hit()
            self.kill()

class Fuel(pygame.sprite.Sprite):
    """Class for fuel cans

    Spawn in random places at the map and can be picked up by one of the players
    The Fuel can is represented by a red/orange rectangle
    """
    def __init__(self, x: int, y: int, size: tuple[int, int], color: tuple[int, int, int]):
        """Create a fuel can at given position with size and color"""
        super().__init__()
        self.image = pygame.Surface(size)
        self.image.fill(color)
        self.rect = self.image.get_rect(topleft=(x, y))



class Ship(pygame.sprite.Sprite):
    """Base sprite class for ships
    
    Keeps the position, velocity, angle, image, and rectagnle data
    The player object inherits from this class and adds its own controls, movement, fuel, shooting
    and collisions
    """
    def __init__(self, x: int, y: int, size: tuple[int, int] = (40, 20)):
        """Create ship sprite at given position"""
        super().__init__()


        ## constants of player
        ###pos
        self.x = x
        self.y = y

        ### vx, vy for velocity in direction
        self.vx = 0.0
        self.vy = 0.0

        self.angle = 0.0

        self.original_image = pygame.Surface(size, pygame.SRCALPHA)
        self.image = self.original_image
        self.rect = self.image.get_rect(center=(round(self.x), round(self.y)))

    def update_rect(self) -> None:
        """Update the sprite rectangle
        
        Only really necassary for the all.sprite.draw(screen)
        """
        self.rect = self.image.get_rect(center=(round(self.x), round(self.y)))


    def move(self) -> None:
        """Move the ship with its velocity"""
        self.x += self.vx
        self.y += self.vy
        self.update_rect()


