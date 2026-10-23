"""Cached metal block artwork. Change blocks here without touching spike art."""

import random

import pygame

from src import visual_style as style


def _shade(color, amount):
    return tuple(max(0, min(255, channel + amount)) for channel in color)


def create_block_surface(rect, destructible=False, damage=0):
    """Both materials share the same steel panels; rust and damage are overlays."""
    surface = pygame.Surface(rect.size)
    # Keep the underlying steel identical for both materials at the same rectangle.
    rng = random.Random(f'block:{rect.x}:{rect.y}:{rect.width}:{rect.height}')
    _draw_metal(surface, rng)
    if destructible:
        _draw_rust(surface, rng)
        if damage:
            draw_block_damage(surface, damage)
    return surface


def _draw_metal(surface, rng):
    width, height = surface.get_size()
    for top in range(0, height, style.PANEL_SPACING):
        for left in range(0, width, style.PANEL_SPACING):
            panel = pygame.Rect(left, top, style.PANEL_SPACING, style.PANEL_SPACING)
            panel = panel.clip(surface.get_rect())
            color = rng.choice(style.METAL_PALETTE)
            # A broad light-to-shadow gradient gives each plate some thickness.
            for y in range(panel.height):
                fraction = y / max(1, panel.height - 1)
                shade = _shade(color, round(style.METAL_SHADE_VARIATION * (1 - 2 * fraction)))
                pygame.draw.line(surface, shade, (panel.left, panel.top + y),
                                 (panel.right - 1, panel.top + y))

    # Smooth, low-contrast staining avoids obvious circles or repeating noise rows.
    wear = _soft_noise(surface.get_size(), style.METAL_WEAR_SCALE, rng)
    wear.set_alpha(style.METAL_WEAR_OPACITY)
    surface.blit(wear, (0, 0))
    for _ in range(width * height // style.GRAIN_AREA):
        x, y = rng.randrange(width), rng.randrange(height)
        shade = _shade(surface.get_at((x, y))[:3],
                       rng.randint(-style.GRAIN_SHADE_VARIATION, style.GRAIN_SHADE_VARIATION))
        pygame.draw.line(surface, shade, (x, y), (x + rng.randint(1, 6), y))

    # Subdued joins and bevels also work where rectangles form connected L/U shapes.
    for x in range(style.PANEL_SPACING, width - 4, style.PANEL_SPACING):
        pygame.draw.line(surface, style.METAL_SEAM, (x, 3), (x, height - 4))
        pygame.draw.line(surface, style.METAL_EDGE, (x + 1, 4), (x + 1, height - 5))
    for y in range(style.PANEL_SPACING, height - 4, style.PANEL_SPACING):
        pygame.draw.line(surface, style.METAL_SEAM, (3, y), (width - 4, y))
    if min(width, height) >= 12:
        pygame.draw.rect(surface, style.METAL_SHADOW, surface.get_rect(), style.BLOCK_BORDER)
        pygame.draw.line(surface, style.METAL_EDGE, (1, 1), (width - 2, 1))
        pygame.draw.line(surface, style.METAL_EDGE, (1, 1), (1, height - 2))
        for x in range(6, width - 3, style.PANEL_SPACING):
            for y in (5, height - 6):
                pygame.draw.circle(surface, style.METAL_SHADOW, (x, y), style.RIVET_RADIUS + 1)
                pygame.draw.circle(surface, style.METAL_RIVET, (x, y), style.RIVET_RADIUS)
    for _ in range(width * height // style.SCRATCH_AREA):
        x, y = rng.randrange(width), rng.randrange(height)
        shade = _shade(surface.get_at((x, y))[:3], rng.choice((-15, 12)))
        pygame.draw.line(surface, shade, (x, y), (x + rng.randint(3, 15), y - 1))


def _soft_noise(size, cell_size, rng):
    """Enlarge a tiny random gray grid into soft, irregular material variation."""
    small = pygame.Surface((max(2, size[0] // cell_size + 1), max(2, size[1] // cell_size + 1)))
    for y in range(small.get_height()):
        for x in range(small.get_width()):
            value = rng.randrange(256)
            small.set_at((x, y), (value, value, value))
    return pygame.transform.smoothscale(small, size)


def _draw_rust(surface, rng):
    width, height = surface.get_size()
    scale = style.RUST_TEXTURE_SCALE
    small_size = (max(1, width // scale), max(1, height // scale))
    noise = _soft_noise(small_size, max(1, style.RUST_PATCH_SCALE // scale), rng)
    rust = pygame.Surface(small_size, pygame.SRCALPHA)
    for y in range(small_size[1]):
        for x in range(small_size[0]):
            panel_x = (x * scale) % style.PANEL_SPACING
            panel_y = (y * scale) % style.PANEL_SPACING
            seam_distance = min(panel_x, style.PANEL_SPACING - panel_x,
                                panel_y, style.PANEL_SPACING - panel_y)
            seam_boost = style.RUST_SEAM_BOOST if seam_distance < style.RUST_SEAM_WIDTH else 0
            # Thresholded soft noise gives broad corrosion with feathered edges.
            level = noise.get_at((x, y))[0] + seam_boost - style.RUST_THRESHOLD
            if level <= 0:
                continue
            alpha = min(style.RUST_MAX_ALPHA, level * style.RUST_ALPHA_SCALE)
            color = rng.choice(style.RUST_PALETTE)
            if rng.random() < style.RUST_PIT_CHANCE:
                color = style.CRACK_COLOR
            rust.set_at((x, y), (*color, alpha))
    surface.blit(pygame.transform.smoothscale(rust, surface.get_size()), (0, 0))


def draw_block_damage(surface, damage):
    """Overlay damage on a copy of the cached, undamaged panel."""
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
