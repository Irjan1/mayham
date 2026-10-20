"""
Base of the code project.

This is the file to run for the game to run.
The file has the main loop of the game.

Authors: Irjan Evertsen and Emil Olsen-Kristiansen
"""

import argparse
import random

import pygame

from config import FPS, FUEL_COLOR, FUEL_SIZE, HEIGHT, OBSTACLE_COLOR, TITLE, WIDTH
from src.arena import (
    ARENA_STYLES, ArenaLayout, choose_fuel_position, create_fixed_arena, generate_arena,
    get_fuel_positions,
)
from src.game_events import GameEvents
from src.gui import NeedsDisplay, Scoreboard, WinnerAnnouncement
from src.geometry import circle_intersects_rect
from src.objects import Fuel, Hazard, Obstacle
from src.player import Player1, Player2


class Game:
    """
    Main game object. The game object sets up pygame, loads assets, processes events,
    updates screen and renders the screen.
    """

    def __init__(self, seed: int | None = None, fixed_arena: bool = False,
                 style: str | None = None) -> None:
        """Initializes pygame, creates game object."""
        pygame.init()
        self.game_events = GameEvents()
        self.fixed_arena = fixed_arena
        self.arena_style = style
        self.next_arena_seed = seed if seed is not None else random.SystemRandom().randrange(2 ** 32)

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(TITLE)

        self.clock = pygame.time.Clock()
        self.running = True

        self.winner_show_delay = 200
        self.winner_choose_delay = 3000

        self.fuel_spawn_time = 10000
        self.time_from_fuel_spawn = pygame.time.get_ticks()

        self.start_new_round()

    def start_new_round(self) -> None:
        """Reset winner state and create fresh game objects for a new round."""
        self.game_events.reset_game_winner()
        self.arena_seed = self.next_arena_seed
        self.next_arena_seed += 1
        arena = create_fixed_arena() if self.fixed_arena else generate_arena(self.arena_seed, self.arena_style)
        print(f"Arena seed: {self.arena_seed} ({arena.style})")
        # This stream is separate from arena generation and global random state.
        self.fuel_rng = random.Random(self.arena_seed)
        self.game_objects(arena)
        self.time_from_fuel_spawn = pygame.time.get_ticks()

    def game_objects(self, arena: ArenaLayout) -> None:
        """Create players, obstacles and sprite groups from the arena layout."""
        if hasattr(self, "players"):
            for group in (self.players, self.obstacles, self.hazards, self.bullets, self.fuel_cans):
                for sprite in group:
                    sprite.kill()

        self.arena = arena
        self.fuel_positions = get_fuel_positions(arena)
        self.player1 = Player1(*arena.player1_spawn)
        self.player2 = Player2(*arena.player2_spawn)

        self.needs_display = NeedsDisplay(self.player1, self.player2)
        self.scoreboard = Scoreboard()

        self.players = pygame.sprite.Group()
        self.players.add(self.player1, self.player2)

        self.obstacles = pygame.sprite.Group()
        for rect in arena.obstacles:
            obstacle = Obstacle(
                rect.x, rect.y, rect.size, OBSTACLE_COLOR,
                destructible=rect in arena.destructible_obstacles,
            )
            self.obstacles.add(obstacle)

        self.hazards = pygame.sprite.Group()
        for rect in arena.hazards:
            self.hazards.add(Hazard(rect))
        self.bullets = pygame.sprite.Group()
        self.fuel_cans = pygame.sprite.Group()

        self.all_sprites = pygame.sprite.Group()
        self.all_sprites.add(self.obstacles, self.hazards, self.players)

    def run(self) -> None:
        """Running of the main game loop."""
        while self.running:
            self.clock.tick(FPS)

            self.handle_events()
            self.update_game()
            self.draw()

        pygame.quit()

    def handle_events(self) -> None:
        """Handling of pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def update_game(self) -> None:
        """Update players, fuel, bullets and winner logic."""
        keys = pygame.key.get_pressed()

        winner = self.game_events.get_game_winner()
        if winner is None:
            self.players.update(
                keys,
                self.obstacles,
                self.players,
                self.bullets,
                self.fuel_cans,
                self.game_events,
            )
            if self.game_events.get_game_winner() is None:
                for player in self.players:
                    if any(circle_intersects_rect((player.x, player.y), player.radius, hazard.rect)
                           for hazard in self.hazards):
                        opponent = player.get_opponent(self.players)
                        self.game_events.hazard_hit_player(player, opponent)
                        break

            if self.game_events.get_game_winner() is None:
                obstacle_count = len(self.obstacles)
                self.bullets.update(self.players, self.obstacles, self.game_events)
                if len(self.obstacles) != obstacle_count:
                    # Removing blocks can open new safe routes. Keep the original
                    # seeded layout intact, and prepare fuel from live rectangles.
                    self.fuel_positions = get_fuel_positions(
                        self.arena, [obstacle.rect for obstacle in self.obstacles],
                    )

        self.spawn_fuel()
        self.all_sprites.add(self.bullets)

        winner = self.game_events.get_game_winner()
        winner_time = self.game_events.get_game_winner_time()

        if winner is not None and winner_time is not None:
            self.handle_winner_time(winner_time)

    def spawn_fuel(self) -> None:
        """Spawn one fuel can if none exists and enough time has passed."""
        current_time = pygame.time.get_ticks()

        if len(self.fuel_cans) == 0 and current_time - self.time_from_fuel_spawn > self.fuel_spawn_time:
            position = choose_fuel_position(
                self.fuel_positions,
                [(player.x, player.y) for player in self.players],
                self.fuel_rng,
            )
            if position is None:
                return
            fuel = Fuel(*position, FUEL_SIZE, FUEL_COLOR)
            self.fuel_cans.add(fuel)
            self.all_sprites.add(fuel)
            self.time_from_fuel_spawn = current_time

    def handle_winner_time(self, winner_time: int) -> None:
        """Start a new round after winner has been shown."""
        current_time = pygame.time.get_ticks()
        time_since_winner = current_time - winner_time

        if time_since_winner >= self.winner_show_delay + self.winner_choose_delay:
            self.start_new_round()

    def draw(self) -> None:
        """Draw all sprites, the GUI and winner."""
        self.screen.fill("black")

        self.all_sprites.draw(self.screen)
        self.needs_display.draw(self.screen)
        self.scoreboard.draw(self.screen)

        winner = self.game_events.get_game_winner()
        winner_time = self.game_events.get_game_winner_time()

        if winner is not None and winner_time is not None:
            current_time = pygame.time.get_ticks()
            time_since_winner = current_time - winner_time

            if time_since_winner >= self.winner_show_delay:
                winner_announcment = WinnerAnnouncement(winner)
                winner_announcment.draw(self.screen)

        pygame.display.flip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mayham: two-player rocket combat")
    parser.add_argument("--seed", type=int, help="First arena seed; later rounds increment it")
    parser.add_argument("--fixed-arena", action="store_true", help="Use the original room")
    parser.add_argument("--style", choices=ARENA_STYLES, help="Choose a room style")
    args = parser.parse_args()
    game = Game(seed=args.seed, fixed_arena=args.fixed_arena, style=args.style)
    game.run()
