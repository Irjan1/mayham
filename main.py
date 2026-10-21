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
from src.background import generate_background
from src.effects import ParticleEffects
from src.gui import NeedsDisplay, Scoreboard, UpgradeSelection, WinnerAnnouncement
from src.geometry import circle_intersects_rect
from src.objects import Fuel, Hazard, Obstacle
from src.player import Player1, Player2
from src.upgrades import apply_upgrade, choose_upgrade_offers, create_upgrade_levels


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
        self.effects = ParticleEffects(f"{self.next_arena_seed}:effects")
        self.style_rng = random.Random(f"{self.next_arena_seed}:styles")
        self.upgrade_rng = random.Random(f"{self.next_arena_seed}:upgrades")
        self.style_bag = []
        self.last_arena_style = None
        self.upgrade_levels = {
            "Player1": create_upgrade_levels(),
            "Player2": create_upgrade_levels(),
        }
        self.upgrade_confirmation_delay = 250

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(TITLE)

        self.clock = pygame.time.Clock()
        self.running = True

        self.winner_show_delay = 200
        self.winner_choose_delay = 3000

        self.fuel_spawn_time = 10000
        self.time_from_fuel_spawn = pygame.time.get_ticks()

        self.start_new_round()

    def choose_arena_style(self) -> str:
        """Use each style once per shuffled bag, avoiding a boundary repeat."""
        if self.arena_style is not None:
            return self.arena_style
        if not self.style_bag:
            self.style_bag = list(ARENA_STYLES)
            self.style_rng.shuffle(self.style_bag)
            if len(self.style_bag) > 1 and self.style_bag[0] == self.last_arena_style:
                self.style_bag[0], self.style_bag[1] = self.style_bag[1], self.style_bag[0]
        style = self.style_bag.pop(0)
        self.last_arena_style = style
        return style

    def start_new_round(self) -> None:
        """Reset winner state and create fresh game objects for a new round."""
        self.upgrade_player = None
        self.upgrade_choices = []
        self.upgrade_screen = None
        self.selected_upgrade_index = None
        self.upgrade_selected_time = None
        self.game_events.reset_game_winner()
        self.arena_seed = self.next_arena_seed
        self.next_arena_seed += 1
        if self.fixed_arena:
            arena = create_fixed_arena()
        else:
            arena = generate_arena(self.arena_seed, self.choose_arena_style())
        print(f"Arena seed: {self.arena_seed} ({arena.style})")
        # This stream is separate from arena generation and global random state.
        self.fuel_rng = random.Random(self.arena_seed)
        self.game_objects(arena)
        self.background, self.background_style = generate_background(self.arena_seed, self.screen.get_size())
        self.time_from_fuel_spawn = pygame.time.get_ticks()

    def game_objects(self, arena: ArenaLayout) -> None:
        """Create players, obstacles and sprite groups from the arena layout."""
        if hasattr(self, "players"):
            for group in (self.players, self.obstacles, self.hazards, self.bullets,
                          self.fuel_cans, self.explosions):
                for sprite in group:
                    sprite.kill()

        self.arena = arena
        self.effects.clear()
        self.fuel_positions = get_fuel_positions(arena)
        self.player1 = Player1(*arena.player1_spawn)
        self.player2 = Player2(*arena.player2_spawn)
        self.player1.effects = self.effects
        self.player2.effects = self.effects
        self.player1.apply_upgrades(self.upgrade_levels["Player1"])
        self.player2.apply_upgrades(self.upgrade_levels["Player2"])

        self.needs_display = NeedsDisplay(self.player1, self.player2)
        self.scoreboard = Scoreboard()

        self.players = pygame.sprite.Group()
        self.players.add(self.player1, self.player2)

        self.obstacles = pygame.sprite.Group()
        for rect in arena.obstacles:
            obstacle = Obstacle(
                rect.x, rect.y, rect.size, OBSTACLE_COLOR,
                destructible=rect in arena.destructible_obstacles,
                effects=self.effects,
            )
            self.obstacles.add(obstacle)

        self.hazards = pygame.sprite.Group()
        for rect in arena.hazards:
            self.hazards.add(Hazard(rect))
        self.bullets = pygame.sprite.Group()
        self.fuel_cans = pygame.sprite.Group()
        self.explosions = pygame.sprite.Group()

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
            elif event.type == pygame.KEYDOWN and self.upgrade_player is not None:
                keys = (pygame.K_1, pygame.K_2, pygame.K_3)
                if event.key in keys:
                    self.select_upgrade(keys.index(event.key))

    def update_game(self) -> None:
        """Update the active round, or wait for the losing player's choice."""
        if self.upgrade_player is not None:
            # Only selection feedback advances here. All gameplay state is frozen.
            if self.selected_upgrade_index is not None:
                elapsed = pygame.time.get_ticks() - self.upgrade_selected_time
                if elapsed >= self.upgrade_confirmation_delay:
                    self.start_new_round()
            return

        # Impact flashes can expire during the winner announcement, but not
        # while the upgrade menu has paused the game.
        self.explosions.update()
        self.effects.update(self.clock.get_time() / 1000)
        winner_time = self.game_events.get_game_winner_time()
        if winner_time is not None:
            self.handle_winner_time(winner_time)
            return

        keys = pygame.key.get_pressed()
        self.players.update(
            keys, self.obstacles, self.players, self.bullets,
            self.fuel_cans, self.game_events,
        )
        if self.game_events.get_game_winner_time() is None:
            for player in self.players:
                if any(circle_intersects_rect((player.x, player.y), player.radius, hazard.rect)
                       for hazard in self.hazards):
                    opponent = player.get_opponent(self.players)
                    self.game_events.hazard_hit_player(player, opponent)
                    break

        if self.game_events.get_game_winner_time() is None:
            obstacle_count = len(self.obstacles)
            self.bullets.update(self.players, self.obstacles, self.game_events, self.explosions)
            if len(self.obstacles) != obstacle_count:
                # Keep the seeded layout intact; prepare fuel from live rectangles.
                self.fuel_positions = get_fuel_positions(
                    self.arena, [obstacle.rect for obstacle in self.obstacles],
                )

        self.all_sprites.add(self.bullets, self.explosions)
        winner_time = self.game_events.get_game_winner_time()
        if winner_time is None:
            self.spawn_fuel()
        else:
            self.handle_winner_time(winner_time)

    def spawn_fuel(self) -> None:
        """Spawn one fuel can if none exists and enough active-round time has passed."""
        if self.upgrade_player is not None or self.game_events.get_game_winner_time() is not None:
            return
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
        """After the winner announcement, offer an upgrade or skip to the next round."""
        if self.upgrade_player is not None or self.game_events.get_game_winner_time() != winner_time:
            return
        elapsed = pygame.time.get_ticks() - winner_time
        if elapsed < self.winner_show_delay + self.winner_choose_delay:
            return

        winner = self.game_events.get_game_winner()
        if winner is None:
            self.start_new_round()
            return
        loser = "Player2" if winner is self.player1 else "Player1"
        choices = choose_upgrade_offers(self.upgrade_levels[loser], self.upgrade_rng)
        if not choices:
            self.start_new_round()
            return
        self.upgrade_player = loser
        self.upgrade_choices = choices
        self.upgrade_screen = UpgradeSelection(loser, choices, self.upgrade_levels[loser])

    def select_upgrade(self, index: int) -> None:
        """Accept exactly one offered card, then briefly show the selection."""
        if self.upgrade_player is None or self.selected_upgrade_index is not None:
            return
        if not 0 <= index < len(self.upgrade_choices):
            return
        upgrade_id = self.upgrade_choices[index]
        if apply_upgrade(self.upgrade_levels[self.upgrade_player], upgrade_id):
            self.selected_upgrade_index = index
            self.upgrade_selected_time = pygame.time.get_ticks()

    def draw(self) -> None:
        """Draw all sprites, the GUI and winner."""
        self.screen.fill("black")
        if self.upgrade_player is not None:
            self.scoreboard.draw(self.screen)
            self.upgrade_screen.draw(self.screen, self.selected_upgrade_index)
            pygame.display.flip()
            return

        self.screen.blit(self.background, (0, 0))
        # Keep all particles behind rockets, bullets, cover, hazards and pickups.
        self.effects.draw(self.screen)
        self.all_sprites.draw(self.screen)
        self.needs_display.draw(self.screen)
        self.scoreboard.draw(self.screen)

        winner = self.game_events.get_game_winner()
        winner_time = self.game_events.get_game_winner_time()

        if winner_time is not None:
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
