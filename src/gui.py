"""
GUI helpers for the game

This file contains classes for drawing GUI elements

Also contains GUI classes for the visual health, fuel, and winner announcment

Authors: Irjan Evertsen and Emil Olsen-Kristiansen
"""

from __future__ import annotations

import pygame # type: ignore

from config import HEIGHT, WIDTH
from src.game_events import GameEvents
from src.upgrades import UPGRADES

class NeedsDisplay:
	"""Display health and fuel for both players."""

	def __init__(self, player1, player2) -> None:
		"""Create the needs display for the players"""
		self.player1 = player1
		self.player2 = player2
		self.font = pygame.font.SysFont(None, 28)
		self.player1_color = (80, 160, 255)
		self.player2_color = (255, 90, 90)

	def draw(self, screen: pygame.Surface) -> None:
		"""Draw player health and fuel values on the screen."""
		player1_text = self._create_player_text("Player 1", self.player1)
		player2_text = self._create_player_text("Player 2", self.player2)

		self._draw_text(screen, player1_text, self.player1_color, (20, 20))
		self._draw_text(screen, player2_text, self.player2_color, (WIDTH - 20, 20), align_right=True)

	def _create_player_text(self, label: str, player) -> str:
		"""Create the health and fuel text for one player"""
		return f"{label}  Health: {player.needs.health}/{player.needs.max_health}  Fuel: {player.needs.fuel}"

	def _draw_text(self, screen: pygame.Surface, text: str, color, position, align_right: bool = False) -> None:
		"""Draw the text on the screen at given position"""
		text_surface = self.font.render(text, True, color)
		text_rect = text_surface.get_rect()
		if align_right:
			text_rect.topright = position
		else:
			text_rect.topleft = position
		screen.blit(text_surface, text_rect)


class WinnerAnnouncement:
	"""Display the winning player in a centered box."""

	def __init__(self, winner) -> None:
		"""Create a winner announcment for the winner"""
		self.winner = winner
		self.font = pygame.font.SysFont(None, 100)
		self.box_color = (25, 25, 25)
		self.border_color = (255, 255, 255)
		self.text_color = (255, 255, 255)

	def draw(self, screen: pygame.Surface) -> None:
		"""Draw the winner announcement."""
		text = "Round drawn" if self.winner is None else f"Winner is {self.winner_to_text(self.winner)}"
		text_surface = self.font.render(text, True, self.text_color)
		text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2))

		box_rect = text_rect.inflate(130, 110)
		pygame.draw.rect(screen, self.box_color, box_rect)
		pygame.draw.rect(screen, self.border_color, box_rect, 3)
		screen.blit(text_surface, text_rect)

	@staticmethod
	def winner_to_text(winner) -> str:
		"""Return a readable winner name."""
		return winner.__class__.__name__




class Scoreboard:
	"""Display player scores."""

	def __init__(self) -> None:
		self.font = pygame.font.SysFont(None, 32)
		self.text_color = (255, 255, 255)

	def draw(self, screen: pygame.Surface) -> None:
		"""Draw player scores at the top center of the screen."""
		scores = GameEvents.get_scores()
		text = f"Player 1: {scores['Player1']}  Player 2: {scores['Player2']}"
		text_surface = self.font.render(text, True, self.text_color)
		text_rect = text_surface.get_rect(midtop=(WIDTH // 2, 20))
		screen.blit(text_surface, text_rect)


	


class UpgradeSelection:
    """Draw the losing player's offers; input and round changes stay in Game."""

    def __init__(self, player_name, choices, levels):
        self.player_name = player_name.replace("Player", "Player ")
        self.choices = choices.copy()
        # Snapshot offered levels so a selected card keeps showing what was bought.
        self.levels = levels.copy()
        self.color = (80, 160, 255) if player_name == "Player1" else (255, 90, 90)
        self.title_font = pygame.font.SysFont(None, 52)
        self.card_font = pygame.font.SysFont(None, 32)
        self.text_font = pygame.font.SysFont(None, 25)
        self.number_font = pygame.font.SysFont(None, 48)

    def draw(self, screen, selected_index=None) -> None:
        title = self.title_font.render(f"{self.player_name}: choose an upgrade", True, self.color)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 140)))
        keys = " / ".join(str(index + 1) for index in range(len(self.choices)))
        prompt = self.text_font.render(f"Press {keys}", True, "white")
        screen.blit(prompt, prompt.get_rect(center=(WIDTH // 2, 195)))

        card_width, card_height, gap = 300, 260, 24
        total_width = len(self.choices) * card_width + (len(self.choices) - 1) * gap
        left = (WIDTH - total_width) // 2
        for index, upgrade_id in enumerate(self.choices):
            upgrade = UPGRADES[upgrade_id]
            level = self.levels.get(upgrade_id, 0) + 1
            rect = pygame.Rect(left + index * (card_width + gap), 250, card_width, card_height)
            selected = index == selected_index
            border = self.color if selected else (100, 100, 100)
            pygame.draw.rect(screen, (25, 25, 25), rect)
            pygame.draw.rect(screen, border, rect, 4 if selected else 2)
            lines = (
                (self.number_font, str(index + 1), 36),
                (self.card_font, upgrade["name"], 88),
                (self.text_font, f"Level {level} / {upgrade['max_level']}", 132),
                (self.text_font, upgrade["effects"][level - 1], 174),
            )
            for font, text, offset in lines:
                label = font.render(text, True, "white")
                screen.blit(label, label.get_rect(center=(rect.centerx, rect.top + offset)))
            if selected:
                label = self.text_font.render("Selected", True, self.color)
                screen.blit(label, label.get_rect(center=(rect.centerx, rect.top + 225)))

        note = self.text_font.render("Your choice stays active in later rounds.", True, (180, 180, 180))
        screen.blit(note, note.get_rect(center=(WIDTH // 2, 565)))
