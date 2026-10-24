"""Static industrial spike art, independent of block textures and damage."""

import pygame # type: ignore

from src import visual_style as style


def draw_hazard(surface, rect):
    """Keep the existing upward teeth and rectangular lethal-zone silhouette."""
    previous_clip = surface.get_clip()
    surface.set_clip(rect.clip(previous_clip))
    pygame.draw.rect(surface, style.SPIKE_BED, rect)
    for x in range(rect.left, rect.right, style.SPIKE_SPACING):
        tip = (min(x + style.SPIKE_SPACING // 2, rect.right - 1), rect.top)
        left = (x, rect.bottom - 1)
        right = (min(x + style.SPIKE_SPACING, rect.right - 1), rect.bottom - 1)
        pygame.draw.polygon(surface, style.SPIKE_STEEL, [left, tip, right])
        pygame.draw.polygon(surface, style.SPIKE_SHADOW,
                            [tip, (tip[0], rect.bottom - 1), right])
        pygame.draw.line(surface, style.SPIKE_RED, left, tip, 2)
        tip_height = max(2, rect.height // 4)
        pygame.draw.polygon(surface, style.SPIKE_RED,
                            [tip, (tip[0] - 2, tip[1] + tip_height),
                             (tip[0] + 2, tip[1] + tip_height)])
        pygame.draw.line(surface, style.SPIKE_HIGHLIGHT, tip,
                         (tip[0] - 2, tip[1] + tip_height), 1)
    mount = pygame.Rect(rect.left, max(rect.top, rect.bottom - style.SPIKE_MOUNT_HEIGHT),
                        rect.width, min(rect.height, style.SPIKE_MOUNT_HEIGHT))
    pygame.draw.rect(surface, style.SPIKE_MOUNT, mount)
    pygame.draw.line(surface, style.SPIKE_RED, mount.topleft, (mount.right - 1, mount.top))
    pygame.draw.rect(surface, style.SPIKE_RED, rect, style.SPIKE_EDGE_WIDTH)
    surface.set_clip(previous_clip)
