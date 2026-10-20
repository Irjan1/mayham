"""
This file contains the player script, classes, and needs object of the game

Player class handles the shared player behaviour
Player1 and Player2 inherit from Player and contain their own controls and the color of the player

@AUTHORS: Irjan Evertsen and Emil Olsen-Kristiansen
"""

import math
import pygame

from config import (
    BULLET_COOLDOWN, FUEL_COOLDOWN, GRAVITY, HEIGHT, PLAYER_RADIUS,
    STARTING_FUEL, STARTING_HEALTH, THRUST, WIDTH,
)
from src.objects import Ship, Obstacle, Bullet
from src.geometry import circle_intersects_rect
from src.upgrades import effective_stats


class Player(Ship):
    """Base player class, hsa shared player behaviour like movement, gravity, collisions,
    fuel usage, shooting, image rotation, and drawing
    """
    def __init__(self, x, y, color, controls):
        """Initialize a player at the given position with the right color and controls"""
        super().__init__(x,y, size=(40,40))

        self.controls = controls
        self.color = color

        #player constants
        self.rotation_speed = 3
        self.thrust = THRUST
        self.radius = PLAYER_RADIUS
        self.gravity = GRAVITY

        # Needs holder fuel og health for enhver spiller
        self.needs = Needs()
        self.is_alive = True

        ## fuel cooldown makes the fuel drain less time per frame
        self.fuel_cooldown = FUEL_COOLDOWN
        self.last_fuel = 0

        self.bullet_cooldown = BULLET_COOLDOWN
        self.last_shot = 0
        self.wall_damage_cooldown = 500
        self.last_wall_damage = -self.wall_damage_cooldown

        # update player image
        self.original_image = self.create_ship_surface()
        self.image = self.original_image
        self.update_rect()


    def apply_upgrades(self, levels: dict[str, int]) -> None:
        """Set fresh round stats from persistent levels, without compounding."""
        stats = effective_stats(levels)
        self.needs.max_health = stats["max_health"]
        self.needs.health = self.needs.max_health
        self.bullet_cooldown = stats["bullet_cooldown"]
        self.thrust = stats["thrust"]

    def create_ship_surface(self) -> pygame.Surface:
        """Create and return the triangular player image"""
        surface = pygame.Surface((40,40), pygame.SRCALPHA)
        pygame.draw.polygon(surface, self.color, [(20,0), (5,35),(35,35)])
        pygame.draw.rect(surface, "white", (17, 10, 6, 6))
        return surface

    def collision(self, obstacle) -> bool:
        """Returns True if the player hitbox collides with an obstacle
        
        Contains the collision logic for circle-rectange collision
        """
        return circle_intersects_rect((self.x, self.y), self.radius, obstacle.rect)

    def inside_screen(self) -> None:
        """Keeps the player inside the screen
        
        Uses the circular hitbox of the player
        """
        if self.x - self.radius < 0:
            self.x = self.radius
            self.vx = -self.vx / 4

        if self.x + self.radius > WIDTH:
            self.x = WIDTH - self.radius
            self.vx = -self.vx / 4

        if self.y - self.radius < 0:
            self.y = self.radius
            self.vy = -self.vy / 4

        if self.y + self.radius > HEIGHT:
            self.y = HEIGHT - self.radius
            self.vy = -self.vy / 4

        self.update_rect()

    def shoot(self, bullets) -> None:
        """Shoots a bullet if the cooldown check passes"""
        time = pygame.time.get_ticks()

        if time - self.last_shot < self.bullet_cooldown:
            return


        bullet = Bullet(self.x, self.y, self.angle, self)
        bullets.add(bullet)

        self.last_shot = time

    def pick_up_fuel(self, fuel_cans) -> None:
        """Checks for player collision with fuel, adds fuel if collision"""
        fuel_touch = pygame.sprite.spritecollide(self, fuel_cans, True, pygame.sprite.collide_circle)

        ## change this with needs object
        if fuel_touch:
            self.needs.add_fuel(STARTING_FUEL // 2)


    def update(self, keys, obstacles, players, bullets, fuel_cans, game_events) -> None:
        """Updates the player every frame
        
        Updates gravity, movement, screen bounds, input, image rotation,
        collision and fuel
        """
        #rotation
        old_x = self.x
        old_y = self.y

        # gravity
        self.vy += self.gravity

        # check for fuel
        self.pick_up_fuel(fuel_cans)

        #movement
        self.move()

        moved_x = self.x
        moved_y = self.y
        self.inside_screen()
        if self.x != moved_x or self.y != moved_y:
            self.take_wall_or_obstacle_damage(players, game_events)

        #input
        self.handle_input(keys, bullets)

        # rotate playerimage
        self.image = pygame.transform.rotate(self.original_image, self.angle)
        self.update_rect()

        for obstacle in obstacles:
            if self.collision(obstacle):
                self.undo_movement(old_x, old_y)
                self.take_wall_or_obstacle_damage(players, game_events)

        sprite_collision = pygame.sprite.spritecollide(self, players, False, pygame.sprite.collide_circle)


        for player in sprite_collision:
            if player != self:
                self.undo_movement(old_x, old_y)
                break

    def take_wall_or_obstacle_damage(self, players, game_events) -> None:
        current_time = pygame.time.get_ticks()

        if current_time - self.last_wall_damage < self.wall_damage_cooldown:
            return

        opponent = self.get_opponent(players)
        game_events.wall_or_obstacle_damage(self, opponent)
        self.last_wall_damage = current_time

    def get_opponent(self, players):
        for player in players:
            if player != self:
                return player
        return None


    def undo_movement(self, old_x, old_y) -> None:
        """Moves the player back to its old position and flips its velocity"""
        self.x = old_x
        self.y = old_y
        self.vx = -self.vx
        self.vy = -self.vy + 1
        self.update_rect()

    def handle_input(self, keys, bullets) -> None:
        """Handles the player input for rotation, thrust, fuel, and shooting"""
        if keys[self.controls["left"]]:
            self.angle += self.rotation_speed

        if keys[self.controls["right"]]:
            self.angle -= self.rotation_speed

        if keys[self.controls["up"]] and self.needs.has_fuel():
            radians = math.radians(self.angle)
            self.vx -= (math.sin(radians) * self.thrust)/3
            self.vy -= math.cos(radians) * self.thrust
            
            curr_time = pygame.time.get_ticks()

            if curr_time - self.last_fuel >= self.fuel_cooldown:
                self.needs.use_fuel(1)
                self.last_fuel = curr_time
        
        if keys[self.controls["shoot"]]:
            self.shoot(bullets)




class Player1(Player):
    """Player 1 controlled by arrow keys and right shift"""
    def __init__(self, x: float, y: float) -> None:
        """Create player1 with color and controls"""
        controls = {
            "left": pygame.K_LEFT,
            "right": pygame.K_RIGHT,
            "up": pygame.K_UP,
            "shoot": pygame.K_RSHIFT,
        }

        super().__init__(x, y, "blue", controls)



class Player2(Player):
    """Player 2 controlled by WASD and SPACE"""
    def __init__(self, x: float, y: float) -> None:
        """Create player2 with color and controls"""
        controls = {
            "left": pygame.K_a,
            "right": pygame.K_d,
            "up": pygame.K_w,
            "shoot": pygame.K_SPACE,
        }

        super().__init__(x, y, "red", controls)


class Needs:
    """Keeps the health and fuel for each player"""
    def __init__(self) -> None:
        self.max_fuel = STARTING_FUEL
        self.fuel = STARTING_FUEL
        self.max_health = STARTING_HEALTH
        self.health = self.max_health

    def has_fuel(self) -> bool:
        """Returns true if the player still has fuel"""
        return self.fuel > 0
    
    def use_fuel(self, amount: int) -> None:
        """Method for player using fuel, used by thrust"""
        self.fuel = max(0, (self.fuel - amount))

    def add_fuel(self, amount: int) -> None:
        """Adds fuel to the player by the given amount"""
        self.fuel = min(self.max_fuel, self.fuel + amount)
