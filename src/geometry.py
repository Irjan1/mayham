"""Collision geometry shared by player collisions and arena validation."""

import pygame


def circle_intersects_rect(center, radius: float, rect: pygame.Rect) -> bool:
    """Use the nearest rectangle point; exact tangency is not a collision."""
    x, y = center
    closest_x = max(rect.left, min(x, rect.right))
    closest_y = max(rect.top, min(y, rect.bottom))
    dx = x - closest_x
    dy = y - closest_y
    return dx * dx + dy * dy < radius * radius
