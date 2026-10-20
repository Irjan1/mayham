"""Collision geometry shared by player collisions and arena validation."""

import math

import pygame


def circle_intersects_rect(center, radius: float, rect: pygame.Rect) -> bool:
    """Use the nearest rectangle point; exact tangency is not a collision."""
    x, y = center
    closest_x = max(rect.left, min(x, rect.right))
    closest_y = max(rect.top, min(y, rect.bottom))
    dx = x - closest_x
    dy = y - closest_y
    return dx * dx + dy * dy < radius * radius


def circle_rect_contact(center, radius: float, rect: pygame.Rect):
    """Return an outward unit normal and overlap depth, or None without contact."""
    if not circle_intersects_rect(center, radius, rect):
        return None

    x, y = center
    closest_x = max(rect.left, min(x, rect.right))
    closest_y = max(rect.top, min(y, rect.bottom))
    dx = x - closest_x
    dy = y - closest_y
    distance = math.hypot(dx, dy)
    if distance > 0:
        # On a face this is axis-aligned; around a corner it points diagonally.
        return (dx / distance, dy / distance), radius - distance

    # Inside the rectangle, the nearest point is the center itself. Use the
    # nearest face instead, and push far enough to clear it by the full radius.
    faces = (
        (x - rect.left, (-1, 0)),
        (rect.right - x, (1, 0)),
        (y - rect.top, (0, -1)),
        (rect.bottom - y, (0, 1)),
    )
    distance, normal = min(faces, key=lambda face: face[0])
    return normal, radius + distance
