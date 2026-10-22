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
from config import (
    WIDTH, HEIGHT, BULLETSPEED, BULLET_RADIUS, BULLET_DAMAGE,
    DESTRUCTIBLE_HITS, EXPLOSION_LIFETIME,
)
from src.block_art import create_block_surface
from src.geometry import circle_rect_contact
from src.hazard_art import draw_hazard

class Obstacle(pygame.sprite.Sprite):
    """A static rectangular obstacle that ships can collide with."""

    def __init__(self, x: int, y: int, size: tuple[int, int], color: tuple[int, int, int],
                 destructible: bool = False, effects=None):
        """Create an obstacle; keep the old color argument for existing callers."""
        super().__init__()

        self.destructible = destructible
        self.effects = effects
        self.hits_remaining = DESTRUCTIBLE_HITS if destructible else 0
        self.rect = pygame.Rect((x, y), size)
        self.image = create_block_surface(self.rect, destructible)

    def take_bullet_hit(self) -> None:
        """Three hits break cover; reinforced obstacles remain permanent."""
        if not self.destructible:
            return
        self.hits_remaining -= 1
        if self.hits_remaining <= 0:
            if self.effects is not None:
                self.effects.debris(self.rect)
            self.kill()
            return
        self.image = create_block_surface(self.rect, destructible=True,
                                          damage=DESTRUCTIBLE_HITS - self.hits_remaining)


class Hazard(pygame.sprite.Sprite):
    """A visible rectangular spike zone; contact kills a player."""

    def __init__(self, rect: pygame.Rect):
        super().__init__()
        self.rect = rect.copy()
        self.image = pygame.Surface(rect.size)
        draw_hazard(self.image, self.image.get_rect())


class Bullet(pygame.sprite.Sprite):
    """One projectile with size, damage, ricochets and an optional terminal blast."""

    def __init__(self, x: float, y: float, angle: float, owner: pygame.sprite.Sprite,
                 radius: int = BULLET_RADIUS, damage: int = BULLET_DAMAGE,
                 bounces: int = 0, explosion_radius: int = 0, effects=None):
        super().__init__()
        self.x = x
        self.y = y
        self.angle = angle
        self.owner = owner
        self.speed = BULLETSPEED
        self.radius = radius
        self.damage = damage
        self.bounces_remaining = bounces
        self.explosion_radius = explosion_radius
        self.finished = False
        self.effects = effects

        self.image = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        color = "gold" if explosion_radius else "orange"
        pygame.draw.circle(self.image, color, (radius, radius), radius)
        self.rect = self.image.get_rect(center=(round(x), round(y)))

        radians = math.radians(angle)
        self.vx = -math.sin(radians) * self.speed
        self.vy = -math.cos(radians) * self.speed

    def update(self, players, obstacles, game_events, explosions=None) -> None:
        """Move in short steps, checking cover before players at each position."""
        if self.finished or game_events.get_game_winner_time() is not None:
            return
        if self.effects is not None and (self.vx or self.vy):
            self.effects.trail(self)
        # At most one pixel per step prevents jumping across thin obstacles.
        # Read velocity each step so the remaining travel follows a ricochet.
        steps = max(1, math.ceil(math.hypot(self.vx, self.vy)))
        for step in range(steps + 1):
            if step:
                self.x += self.vx / steps
                self.y += self.vy / steps
            self.rect.center = (round(self.x), round(self.y))
            if self.collide_with_surfaces(obstacles):
                self.finish(players, game_events, explosions)
                return
            for player in players:
                if player is self.owner or not player.is_alive:
                    continue
                dx, dy = self.x - player.x, self.y - player.y
                if dx * dx + dy * dy <= (self.radius + player.radius) ** 2:
                    self.finish(players, game_events, explosions, player)
                    return

    def collide_with_surfaces(self, obstacles) -> bool:
        """Resolve contacts; True means a terminal impact rather than a ricochet."""
        contacts = []
        if self.x < self.radius:
            contacts.append(((1, 0), self.radius - self.x))
        if self.x > WIDTH - self.radius:
            contacts.append(((-1, 0), self.x - (WIDTH - self.radius)))
        if self.y < self.radius:
            contacts.append(((0, 1), self.radius - self.y))
        if self.y > HEIGHT - self.radius:
            contacts.append(((0, -1), self.y - (HEIGHT - self.radius)))
        for normal, depth in contacts:
            if not self.bounce(normal, depth):
                return True
        for obstacle in obstacles:
            contact = circle_rect_contact((self.x, self.y), self.radius, obstacle.rect)
            if contact is not None and not self.bounce(*contact, obstacle=obstacle):
                return True
        return False

    def bounce(self, normal, depth, obstacle=None) -> bool:
        """Separate and reflect inward motion, or report exhausted ricochets."""
        nx, ny = normal
        normal_speed = self.vx * nx + self.vy * ny
        if self.effects is not None and (normal_speed < 0 or self.bounces_remaining == 0):
            # The separated center minus the radius lies on the contacted surface.
            position = (self.x + nx * (depth - self.radius),
                        self.y + ny * (depth - self.radius))
            self.effects.impact(position, normal)
        if obstacle is not None and (normal_speed < 0 or self.bounces_remaining == 0):
            obstacle.take_bullet_hit()
        if self.bounces_remaining == 0:
            return False
        # The small gap avoids charging another bounce for round-off overlap.
        self.x += nx * (depth + 1e-6)
        self.y += ny * (depth + 1e-6)
        if normal_speed < 0:
            self.vx -= 2 * normal_speed * nx
            self.vy -= 2 * normal_speed * ny
            self.bounces_remaining -= 1
        self.rect.center = (round(self.x), round(self.y))
        return True

    def finish(self, players, game_events, explosions, direct_target=None) -> None:
        """Damage once at terminal impact; an explosive hit replaces direct damage."""
        if self.finished:
            return
        self.finished = True
        self.kill()
        if self.explosion_radius:
            if explosions is not None:
                explosions.add(Explosion(self.x, self.y, self.explosion_radius))
            # Blasts ignore cover and the shooter. Rendering never applies damage.
            for player in list(players):
                if player is self.owner:
                    continue
                dx, dy = player.x - self.x, player.y - self.y
                if dx * dx + dy * dy <= (self.explosion_radius + player.radius) ** 2:
                    game_events.damage_player(player, self.damage, self.owner)
        elif direct_target is not None:
            game_events.bullet_hit_player(self, direct_target)


class Explosion(pygame.sprite.Sprite):
    """A short-lived circular impact flash; damage has already been applied."""

    def __init__(self, x, y, radius):
        super().__init__()
        self.radius = radius
        self.created_at = pygame.time.get_ticks()
        self.image = pygame.Surface((2 * radius, 2 * radius), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (255, 120, 0, 90), (radius, radius), radius)
        pygame.draw.circle(self.image, (255, 190, 40), (radius, radius), radius, 3)
        pygame.draw.circle(self.image, (255, 240, 160), (radius, radius), radius // 2, 2)
        self.rect = self.image.get_rect(center=(round(x), round(y)))

    def update(self) -> None:
        if pygame.time.get_ticks() - self.created_at >= EXPLOSION_LIFETIME:
            self.kill()


class Fuel(pygame.sprite.Sprite):
    """An orange canister, keeping the original pickup rectangle and collision rule."""

    def __init__(self, x: int, y: int, size: tuple[int, int], color: tuple[int, int, int]):
        super().__init__()
        # Transparent corners change only the drawing, not the pickup rectangle.
        self.image = pygame.Surface(size, pygame.SRCALPHA)
        width, height = size
        dark = (75, 45, 20)
        pygame.draw.rect(self.image, (255, 205, 95), (6, 2, width // 3, 9), 2, border_radius=2)
        pygame.draw.rect(self.image, dark, (width - 11, 3, 7, 7), border_radius=1)
        pygame.draw.rect(self.image, (235, 225, 190), (width - 10, 4, 5, 3))
        body = pygame.Rect(3, 8, width - 6, height - 10)
        pygame.draw.rect(self.image, color, body, border_radius=3)
        pygame.draw.rect(self.image, dark, body, 2, border_radius=3)
        pygame.draw.line(self.image, (255, 215, 125), (6, 11), (6, height - 6))
        center_x, center_y = width // 2, height // 2 + 4
        cream = (255, 245, 205)
        pygame.draw.polygon(self.image, cream, [(center_x, center_y - 7),
                            (center_x - 4, center_y), (center_x + 4, center_y)])
        pygame.draw.circle(self.image, cream, (center_x, center_y), 4)
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


