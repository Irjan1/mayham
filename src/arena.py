"""
Arena geometry, separate from the sprites used to display it.

Authors: Irjan Evertsen
"""

from dataclasses import dataclass

import pygame

from config import HEIGHT, OBSTACLE_SIZE, WIDTH


@dataclass
class ArenaLayout:
    """Obstacle rectangles and player center positions for one round."""

    obstacles: list[pygame.Rect]
    player1_spawn: tuple[int, int]
    player2_spawn: tuple[int, int]


def create_fixed_arena() -> ArenaLayout:
    """Return the original room with one obstacle in the center."""
    obstacle = pygame.Rect(
        (WIDTH - OBSTACLE_SIZE[0]) // 2,
        (HEIGHT - OBSTACLE_SIZE[1]) // 2,
        *OBSTACLE_SIZE,
    )
    return ArenaLayout(
        obstacles=[obstacle],
        player1_spawn=(WIDTH // 4, HEIGHT // 4),
        player2_spawn=(WIDTH * 3 // 4, HEIGHT * 3 // 4),
    )
