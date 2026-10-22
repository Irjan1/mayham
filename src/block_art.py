"""Cached metal block artwork. Change blocks here without touching spike art."""

import random

import pygame

from src import visual_style as style


def _shade(color, amount):
    return tuple(max(0, min(255, channel + amount)) for channel in color)


def create_block_surface(rect, destructible=False, damage=0):
    """Paint a worn panel once, keeping its exact rectangular sprite dimensions."""
    width, height = rect.size
    surface = pygame.Surface(rect.size)
    # Stable cosmetic variation, independent of every gameplay random stream.
    rng = random.Random(f'block:{rect.x}:{rect.y}:{width}:{height}:{destructible}')
    palette = style.COVER_PALETTE if destructible else style.METAL_PALETTE
    edge = style.COVER_EDGE if destructible else style.METAL_EDGE
    shadow = style.COVER_SHADOW if destructible else style.METAL_SHADOW
    seam = style.COVER_SEAM if destructible else style.METAL_SEAM
    rivet = style.COVER_RIVET if destructible else style.METAL_RIVET
    surface.fill(palette[0])

    # Broad uneven patches, then fine grain: worn metal rather than flat tiles.
    y = 0
    while y < height:
        patch_height = rng.randint(*style.PATCH_SIZE)
        x = 0
        while x < width:
            patch_width = rng.randint(*style.PATCH_SIZE)
            color = _shade(rng.choice(palette), rng.randint(-style.PATCH_SHADE_VARIATION,
                                                          style.PATCH_SHADE_VARIATION))
            pygame.draw.rect(surface, color, (x, y, patch_width, patch_height))
            x += patch_width
        y += patch_height
    for y in range(0, height, style.GRAIN_SPACING):
        for x in range(0, width, style.GRAIN_SPACING):
            color = surface.get_at((x, y))[:3]
            shade = _shade(color, rng.randint(-style.GRAIN_SHADE_VARIATION,
                                              style.GRAIN_SHADE_VARIATION))
            pygame.draw.line(surface, shade, (x, y), (x + rng.randint(1, 5), y))

    # Quiet joins and bevels keep connected L/U parts from looking like bright boxes.
    for x in range(style.PANEL_SPACING, width - 4, style.PANEL_SPACING):
        pygame.draw.line(surface, seam, (x, 3), (x, height - 4))
        pygame.draw.line(surface, edge, (x + 1, 4), (x + 1, height - 5))
    for y in range(style.PANEL_SPACING, height - 4, style.PANEL_SPACING):
        pygame.draw.line(surface, seam, (3, y), (width - 4, y))
    if min(width, height) >= 12:
        border = style.BLOCK_BORDER
        pygame.draw.rect(surface, shadow, surface.get_rect(), border)
        pygame.draw.line(surface, edge, (1, 1), (width - 2, 1))
        pygame.draw.line(surface, edge, (1, 1), (1, height - 2))
        for x in range(6, width - 3, style.PANEL_SPACING):
            for y in (5, height - 6):
                pygame.draw.circle(surface, shadow, (x, y), style.RIVET_RADIUS + 1)
                pygame.draw.circle(surface, rivet, (x, y), style.RIVET_RADIUS)
    for _ in range(width * height // style.SCRATCH_AREA):
        x, y = rng.randrange(width), rng.randrange(height)
        color = _shade(surface.get_at((x, y))[:3], rng.choice((-24, 21)))
        pygame.draw.line(surface, color, (x, y), (x + rng.randint(3, 13), y - 1))

    if destructible:
        _draw_cover_details(surface)
        if damage:
            _draw_damage(surface, damage)
    return surface


def _draw_cover_details(surface):
    width, height = surface.get_size()
    if min(width, height) < 12:
        return
    stripe = pygame.Rect(3, height - style.WARNING_HEIGHT - 3, width - 6, style.WARNING_HEIGHT)
    pygame.draw.rect(surface, style.WARNING_DARK, stripe)
    previous_clip = surface.get_clip()
    surface.set_clip(stripe)
    for x in range(-style.WARNING_HEIGHT, width, style.WARNING_SPACING):
        pygame.draw.line(surface, style.WARNING_AMBER, (x, stripe.bottom),
                         (x + style.WARNING_HEIGHT, stripe.top), 4)
    surface.set_clip(previous_clip)
    if width >= 28 and height >= 24:
        # Recessed vents suggest thin machinery covers rather than reinforced walls.
        for offset in (-5, 0, 5):
            y = height // 2 + offset
            pygame.draw.line(surface, style.COVER_SHADOW, (width // 2 - 7, y), (width // 2 + 7, y), 2)


def _draw_damage(surface, damage):
    width, height = surface.get_size()
    if damage >= 2:
        wound = [(width * x, height * y) for x, y in
                 ((0.31, 0.27), (0.60, 0.34), (0.73, 0.60), (0.51, 0.77), (0.29, 0.57))]
        pygame.draw.polygon(surface, style.EXPOSED_INTERIOR, wound)
        pygame.draw.lines(surface, style.CRACK_EDGE, False, wound[:3], 1)
    points = [(round(width * x), round(height * y)) for x, y in
              ((0.55, 0), (0.43, 0.28), (0.59, 0.42), (0.42, 0.70), (0.50, 1))]
    pygame.draw.lines(surface, style.CRACK_COLOR, False, points, 3 if damage == 1 else 5)
    pygame.draw.lines(surface, style.CRACK_EDGE, False,
                      [(x + 2, y) for x, y in points[1:4]], 1)
    pygame.draw.lines(surface, style.CRACK_COLOR, False,
                      [points[2], (width * 0.78, height * 0.35), (width, height * 0.47)], 2)
    if damage >= 2:
        pygame.draw.lines(surface, style.CRACK_COLOR, False,
                          [(0, height * 0.7), points[3], (width * 0.76, height)], 3)
