"""
Game event logic.

This file contains helpers and the GameEvents class, which handles bullet damage,
player death, winner state, scoring, and crash penalties.

Authors: Irjan Evertsen and Emil Olsen-Kristiansen
"""

from __future__ import annotations

import pygame # type: ignore

from config import WALL_DAMAGE


class GameEvents:
    """Handle shared gameplay events."""

    player_scores = {
        "Player1": 0,
        "Player2": 0,
    }

    def __init__(self, audio=None) -> None:
        """Create a game event handler, no winner at the start."""
        self.game_winner_player = None
        self.game_winner_time = None
        self.audio = audio

    def bullet_hit_player(self, bullet, player) -> None:
        """Update player health when hit by a bullet."""
        self.damage_player(player, bullet.damage, bullet.owner)
        bullet.kill()

    def damage_player(self, player, damage, owner) -> None:
        """Apply projectile or blast damage using the same health and scoring rules."""
        if not player.is_alive:
            return
        player.needs.health = max(0, player.needs.health - damage)
        if player.needs.health == 0:
            self.player_died(player, owner)
        elif damage > 0 and self.audio is not None:
            self.audio.play('rocket_hit', source=player)

    def wall_or_obstacle_damage(self, player, killer) -> None:
        """Damage a player after hitting a wall or obstacle."""
        previous_health = player.needs.health
        player.needs.health = max(0, player.needs.health - WALL_DAMAGE)

        if player.needs.health == 0 and player.is_alive:
            self.player_died(player, killer)
        elif player.needs.health < previous_health and self.audio is not None:
            self.audio.play('rocket_hit', source=player)

    def hazard_hit_player(self, player, opponent) -> None:
        """Spike zones are lethal and award the opponent the round."""
        if player.is_alive:
            player.needs.health = 0
            self.player_died(player, opponent)

    def player_died(self, player, killer) -> None:
        """Mark a player as dead and pass the killer to the winner handler."""
        if player.is_alive and self.audio is not None:
            self.audio.play('destruction', source=player)
        player.is_alive = False
        player.kill()
        self.game_winner(killer)

    def game_winner(self, winner) -> None:
        """Store the winner, update score and when the game ended."""
        # A draw has no winning player, but its timestamp still ends the round.
        if self.game_winner_time is not None:
            return

        self.game_winner_player = winner
        self.game_winner_time = pygame.time.get_ticks()
        if self.audio is not None:
            self.audio.stop_engines()

        if winner is None:
            return

        winner_name = winner.__class__.__name__
        if winner_name in self.player_scores:
            self.player_scores[winner_name] += 1

    def get_game_winner(self):
        """Return the winner if the game has ended."""
        return self.game_winner_player

    def get_game_winner_time(self):
        """Return when the winner was decided."""
        return self.game_winner_time

    def reset_game_winner(self) -> None:
        """Clear winner state before a new round starts."""
        self.game_winner_player = None
        self.game_winner_time = None

    @staticmethod # brukes bare for å unngå å bruke objektet ()self)
    def reverse_ship_if_obstacle_hit(ships: pygame.sprite.Group, obstacle: pygame.sprite.Sprite) -> bool:
        """Reverse only ships that collide with the obstacle.

        Returns True if at least one ship changed direction this frame.
        """
        hit_any_ship = False

        for ship in ships:
            if not hasattr(ship, "rect"):
                continue
            if not hasattr(ship, "reverse_direction"):
                continue
            if not hasattr(obstacle, "rect"):
                continue

            if ship.rect.colliderect(obstacle.rect):
                hit_any_ship = True

                if hasattr(ship, "speed_x") and ship.speed_x >= 0:
                    ship.rect.right = obstacle.rect.left
                else:
                    ship.rect.left = obstacle.rect.right

                ship.reverse_direction()

        return hit_any_ship

    @staticmethod # brukes bare for å unngå å bruke objektet ()self)
    def get_scores():
        """Return a copy of the current player scores."""
        return GameEvents.player_scores.copy()


    @staticmethod # brukes bare for å unngå å bruke objektet ()self)
    def reverse_ships_if_edge_hit(ships: pygame.sprite.Group, screen_width: int) -> bool:
        """Reverse all ships when any ship touches a horizontal edge.

        Returns True if a direction change was applied this frame.
        """
        should_reverse = any(
            hasattr(ship, "hits_screen_edge") and ship.hits_screen_edge(screen_width)
            for ship in ships
        )

        if should_reverse:
            for ship in ships:
                if hasattr(ship, "reverse_direction"):
                    ship.reverse_direction()

        return should_reverse
