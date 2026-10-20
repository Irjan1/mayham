"""
Base of the code project.

This is the file to run for the game to run.
The file has the main loop of the game.

Authors: Irjan Evertsen and Emil Olsen-Kristiansen
"""

import pygame

from config import FPS, HEIGHT, OBSTACLE_COLOR, TITLE, WIDTH
from src.arena import ArenaLayout, create_fixed_arena
from src.game_events import GameEvents
from src.gui import NeedsDisplay, ObjectFactory, Scoreboard, WinnerAnnouncement
from src.objects import Obstacle
from src.player import Player1, Player2


class Game:
    """
    Main game object. The game object sets up pygame, loads assets, processes events,
    updates screen and renders the screen.
    """

    def __init__(self) -> None:
        """Initializes pygame, creates game object."""
        pygame.init()
        self.game_events = GameEvents()
        self.object_factory = ObjectFactory()

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
        self.time_from_fuel_spawn = pygame.time.get_ticks()
        self.game_objects(create_fixed_arena())

    def game_objects(self, arena: ArenaLayout) -> None:
        """Create players, obstacles and sprite groups from the arena layout."""
        self.player1 = Player1(*arena.player1_spawn)
        self.player2 = Player2(*arena.player2_spawn)

        self.needs_display = NeedsDisplay(self.player1, self.player2)
        self.scoreboard = Scoreboard()

        self.players = pygame.sprite.Group()
        self.players.add(self.player1, self.player2)

        self.obstacles = pygame.sprite.Group()
        for rect in arena.obstacles:
            obstacle = Obstacle(rect.x, rect.y, rect.size, OBSTACLE_COLOR)
            self.obstacles.add(obstacle)

        self.bullets = pygame.sprite.Group()
        self.fuel_cans = pygame.sprite.Group()

        self.all_sprites = pygame.sprite.Group()
        self.all_sprites.add(self.obstacles, self.players)

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
            self.bullets.update(self.players, self.obstacles, self.game_events)

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
            fuel = self.object_factory.create_fuelcan()
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
    game = Game()
    game.run()
