"""Static procedural space scenery and its PNG preview tool.

All background tuning lives below. Add a style by defining a drawing function,
then adding its name to STYLE_WEIGHTS, STAR_DENSITY and STYLE_DRAWERS.
Preview: python -m src.background --start 0 --count 12 --output backgrounds.png
"""

import argparse
import math
from pathlib import Path
import random

import pygame


# Global fade: both controls run from 0 (black/invisible) to 1 (unfaded).
BRIGHTNESS = 0.70
OPACITY = 0.90
SEED_SALT = 0x4D415948  # Stable integer separation from the arena's random stream.
STYLE_WEIGHTS = {
    "empty": 30, "planet": 25, "galaxy": 15,
    "nebula": 20, "black_hole": 5, "nova": 5,
}
BASE_PALETTES = (
    ((2, 4, 10), (5, 8, 17)), ((3, 3, 8), (10, 6, 14)),
    ((1, 4, 6), (5, 10, 12)),
)

# Stars per million pixels, before each room's density variation.
STAR_DENSITY = {"empty": 220, "planet": 140, "galaxy": 100,
                "nebula": 90, "black_hole": 110, "nova": 90}
STAR_DENSITY_VARIATION = (0.5, 2.2)
STAR_BRIGHTNESS = (22, 85)
STAR_COLORS = ((155, 180, 210), (190, 175, 165), (155, 185, 175))
LARGER_STAR_CHANCE = 0.04
CLUSTER_CHANCE = 0.30
CLUSTER_STARS = 35

# Celestial sizes are fractions of the shorter viewport dimension.
PLANET_RADIUS = (0.20, 0.50)
PLANET_COLORS = ((52, 65, 82), (78, 61, 46), (42, 65, 63), (65, 51, 76))
PLANET_SHADING_STEPS = 36
PLANET_KINDS = ("rocky", "gas", "dark")
RING_CHANCE = 0.35
RING_OUTER_RADIUS = 1.90  # Relative to the planet's radius.
RING_INNER_RADIUS = 1.25
RING_FLATTENING = 0.28
RING_OPACITY = 110
RING_BANDS = 9
RING_TILT = (-35, 35)

# Soft objects are painted small and enlarged once, giving smooth cloud edges.
SOFT_SCALE = 4
GALAXY_RADIUS = (0.32, 0.60)
GALAXY_COLORS = ((80, 88, 105), (94, 77, 91), (92, 84, 66))
GALAXY_OPACITY = 75
GALAXY_FLATTENING = (0.35, 0.65)
GALAXY_SPIRAL_CHANCE = 0.70
GALAXY_ARM_POINTS = 110
NEBULA_COLORS = ((64, 35, 80), (35, 60, 85), (75, 32, 38),
                 (35, 62, 55), (32, 36, 48))
CLOUD_CHAINS = (2, 4)
CLOUD_POINTS = 22
CLOUD_RADIUS = (0.10, 0.23)
CLOUD_OPACITY = 95
DUST_OPACITY = 100

BLACK_HOLE_RADIUS = (0.07, 0.13)
BLACK_HOLE_COLORS = ((110, 78, 50), (78, 65, 105), (55, 85, 110))
BLACK_HOLE_DISK_RADIUS = 2.8
BLACK_HOLE_DISK_OPACITY = 110
NOVA_RADIUS = (0.22, 0.42)
NOVA_COLORS = ((60, 95, 105), (90, 60, 105), (65, 95, 78))
NOVA_OPACITY = 75
NOVA_SHELLS = (0.65, 0.90, 1.10)
NOVA_SHELL_POINTS = 65

# Preview settings affect saved contact sheets only.
PREVIEW_WIDTH = 360
PREVIEW_MARGIN = 12
PREVIEW_CAPTION = 30


def choose_style(rng) -> str:
    """Choose one primary theme, with common quiet scenes and rare dramatic ones."""
    weights = list(STYLE_WEIGHTS.values())
    if not weights or any(weight < 0 for weight in weights) or sum(weights) <= 0:
        raise ValueError("Background weights must be non-negative with a positive total")
    return rng.choices(list(STYLE_WEIGHTS), weights=weights, k=1)[0]


def _glow(surface, center, radius, color, opacity):
    """Blend a soft circular stamp; overlapping stamps form irregular clouds."""
    radius = max(1, round(radius))
    stamp = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
    for ring in range(radius, 0, -1):
        alpha = round(opacity * (1 - ring / (radius + 1)) ** 2)
        pygame.draw.circle(stamp, (*color, alpha), (radius + 1, radius + 1), ring)
    surface.blit(stamp, (round(center[0]) - radius - 1, round(center[1]) - radius - 1))


def _stars(surface, rng, style):
    width, height = surface.get_size()
    density = STAR_DENSITY[style] * rng.uniform(*STAR_DENSITY_VARIATION)
    for _ in range(round(width * height / 1_000_000 * density)):
        position = (rng.randrange(width), rng.randrange(height))
        brightness = rng.randint(*STAR_BRIGHTNESS)
        tint = rng.choice(STAR_COLORS)
        color = tuple(channel * brightness // 255 for channel in tint)
        if rng.random() < LARGER_STAR_CHANCE:
            pygame.draw.circle(surface, color, position, 1)
        else:
            surface.set_at(position, color)


def draw_empty(surface, rng):
    if rng.random() >= CLUSTER_CHANCE:
        return
    width, height = surface.get_size()
    center = (rng.uniform(0, width), rng.uniform(0, height))
    spread = min(width, height) * 0.06
    for _ in range(CLUSTER_STARS):
        x, y = round(rng.gauss(center[0], spread)), round(rng.gauss(center[1], spread))
        if 0 <= x < width and 0 <= y < height:
            shade = rng.randint(18, 40)
            surface.set_at((x, y), (shade, shade, shade + 5))


def _planet_rings(radius, color, tilt):
    """Split the disk before tilting so its front arc can cross the planet."""
    outer = round(radius * RING_OUTER_RADIUS)
    rings = pygame.Surface((outer * 2 + 4, round(outer * 2 * RING_FLATTENING) + 4), pygame.SRCALPHA)
    center_x, center_y = rings.get_width() // 2, rings.get_height() // 2
    for band in range(RING_BANDS):
        fraction = band / max(1, RING_BANDS - 1)
        ring_radius = radius * (RING_OUTER_RADIUS + fraction * (RING_INNER_RADIUS - RING_OUTER_RADIUS))
        rect = pygame.Rect(0, 0, round(2 * ring_radius), max(2, round(2 * ring_radius * RING_FLATTENING)))
        rect.center = (center_x, center_y)
        pygame.draw.ellipse(rings, (*color, RING_OPACITY), rect, max(1, round(radius * 0.012)))
    front = pygame.Surface(rings.get_size(), pygame.SRCALPHA)
    front.blit(rings, (0, center_y), pygame.Rect(0, center_y, rings.get_width(), rings.get_height() - center_y))
    return pygame.transform.rotate(rings, tilt), pygame.transform.rotate(front, tilt)


def draw_planet(surface, rng):
    width, height = surface.get_size()
    radius = max(4, round(min(width, height) * rng.uniform(*PLANET_RADIUS)))
    center = (round(width * rng.choice((rng.uniform(0.04, 0.28), rng.uniform(0.72, 0.96)))),
              round(height * rng.uniform(0.15, 0.95)))
    color = rng.choice(PLANET_COLORS)
    kind = rng.choice(PLANET_KINDS)
    if kind == "dark":
        color = tuple(channel // 3 for channel in color)
    planet = pygame.Surface((radius * 2 + 6, radius * 2 + 6), pygame.SRCALPHA)
    local_center = (radius + 3, radius + 3)
    pygame.draw.circle(planet, (*color, 80), local_center, radius + 2, 2)
    for step in range(PLANET_SHADING_STEPS):
        progress = step / PLANET_SHADING_STEPS
        shade = tuple(round(channel * (0.18 + 0.82 * progress)) for channel in color)
        point = (round(local_center[0] - radius * 0.25 * progress),
                 round(local_center[1] - radius * 0.18 * progress))
        pygame.draw.circle(planet, shade, point, max(1, round(radius * (1 - progress))))
    texture = pygame.Surface(planet.get_size(), pygame.SRCALPHA)
    if kind == "gas":
        band_width = max(2, radius // 12)
        for y in range(0, radius * 2 + 6, band_width * 2):
            points = [(x, round(y + math.sin(x / radius * 3 + y) * radius * 0.035))
                      for x in range(0, radius * 2 + 7, max(1, radius // 5))]
            pygame.draw.lines(texture, (*color, rng.randint(35, 75)), False, points, band_width)
    elif kind == "rocky":
        for _ in range(45):
            point = (rng.randrange(planet.get_width()), rng.randrange(planet.get_height()))
            pygame.draw.circle(texture, (5, 7, 12, 60), point, max(1, round(radius * rng.uniform(0.02, 0.08))))
    planet.blit(texture, (0, 0))
    mask = pygame.Surface(planet.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(mask, "white", local_center, radius + 2)
    planet.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    ringed = rng.random() < RING_CHANCE
    if ringed:
        ring_color = tuple(min(130, channel + 30) for channel in color)
        back, front = _planet_rings(radius, ring_color, rng.uniform(*RING_TILT))
        surface.blit(back, back.get_rect(center=center))
    surface.blit(planet, planet.get_rect(center=center))
    if ringed:
        surface.blit(front, front.get_rect(center=center))


def draw_galaxy(surface, rng):
    width, height = surface.get_size()
    radius = max(4, round(min(width, height) * rng.uniform(*GALAXY_RADIUS) / SOFT_SCALE))
    layer = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
    center = (radius + 1, radius + 1)
    color = rng.choice(GALAXY_COLORS)
    _glow(layer, center, radius, color, GALAXY_OPACITY)
    if rng.random() < GALAXY_SPIRAL_CHANCE:
        arms = rng.choice((2, 3))
        for arm in range(arms):
            for point in range(GALAXY_ARM_POINTS):
                progress = (point + 1) / GALAXY_ARM_POINTS
                angle = arm * math.tau / arms + progress * math.tau * 1.2 + rng.uniform(-0.12, 0.12)
                distance = radius * progress
                position = (center[0] + math.cos(angle) * distance,
                            center[1] + math.sin(angle) * distance)
                _glow(layer, position, max(1, radius * 0.10 * (1 - progress) + 1), color, GALAXY_OPACITY)
    _glow(layer, center, max(2, radius * 0.22), (105, 105, 120), GALAXY_OPACITY)
    # A faint offset dust lane breaks the symmetry of the distant light.
    for point in range(15):
        _glow(layer, (center[0] - radius * 0.7 + point * radius * 0.1,
                      center[1] + math.sin(point / 4) * radius * 0.12),
              max(1, radius * 0.045), (2, 3, 7), DUST_OPACITY)
    size = (layer.get_width() * SOFT_SCALE,
            max(1, round(layer.get_height() * SOFT_SCALE * rng.uniform(*GALAXY_FLATTENING))))
    layer = pygame.transform.rotate(pygame.transform.smoothscale(layer, size), rng.uniform(-50, 50))
    surface.blit(layer, layer.get_rect(center=(round(width * rng.uniform(0.25, 0.75)),
                                              round(height * rng.uniform(0.25, 0.75)))))


def draw_nebula(surface, rng):
    width, height = surface.get_size()
    small_size = (max(1, width // SOFT_SCALE), max(1, height // SOFT_SCALE))
    layer = pygame.Surface(small_size, pygame.SRCALPHA)
    color = rng.choice(NEBULA_COLORS)
    angle = rng.uniform(0, math.tau)
    for chain in range(rng.randint(*CLOUD_CHAINS)):
        center_x = rng.uniform(0, small_size[0])
        center_y = rng.uniform(0, small_size[1])
        for point in range(CLOUD_POINTS):
            distance = (point / (CLOUD_POINTS - 1) - 0.5) * max(small_size) * 1.4
            bend = math.sin(point * 0.35 + chain) * small_size[1] * 0.2
            position = (center_x + math.cos(angle) * distance - math.sin(angle) * bend,
                        center_y + math.sin(angle) * distance + math.cos(angle) * bend)
            radius = min(small_size) * rng.uniform(*CLOUD_RADIUS)
            _glow(layer, position, radius, color, CLOUD_OPACITY)
            if point % 3 == 0:
                _glow(layer, (position[0] + radius * 0.3, position[1]), radius * 0.6,
                      (1, 2, 5), DUST_OPACITY)
    surface.blit(pygame.transform.smoothscale(layer, (width, height)), (0, 0))


def draw_black_hole(surface, rng):
    width, height = surface.get_size()
    radius = max(4, round(min(width, height) * rng.uniform(*BLACK_HOLE_RADIUS)))
    color = rng.choice(BLACK_HOLE_COLORS)
    outer = round(radius * BLACK_HOLE_DISK_RADIUS)
    disk = pygame.Surface((outer * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
    disk_center = disk.get_rect().center
    for band in range(18):
        fraction = band / 18
        rect = pygame.Rect(0, 0, round(outer * 2 * (1 - fraction * 0.55)),
                           max(2, round(radius * (0.85 - fraction * 0.35))))
        rect.center = disk_center
        pygame.draw.ellipse(disk, (*color, BLACK_HOLE_DISK_OPACITY), rect, max(1, radius // 35))
    disk = pygame.transform.rotate(disk, rng.uniform(-35, 35))
    center = (round(width * rng.uniform(0.25, 0.75)), round(height * rng.uniform(0.25, 0.75)))
    surface.blit(disk, disk.get_rect(center=center))
    pygame.draw.circle(surface, (1, 2, 4), center, radius)
    arc = pygame.Rect(0, 0, radius * 2 + 8, radius * 2 + 8)
    arc.center = center
    pygame.draw.arc(surface, tuple(channel // 3 for channel in color), arc, 0.15, math.pi - 0.15, 2)


def draw_nova(surface, rng):
    width, height = surface.get_size()
    radius = max(4, round(min(width, height) * rng.uniform(*NOVA_RADIUS) / SOFT_SCALE))
    layer = pygame.Surface((radius * 3, radius * 3), pygame.SRCALPHA)
    center = layer.get_rect().center
    color = rng.choice(NOVA_COLORS)
    phase = rng.uniform(0, math.tau)
    for shell in NOVA_SHELLS:
        for point in range(NOVA_SHELL_POINTS):
            if rng.random() < 0.15:
                continue  # Broken filaments, rather than a crisp gameplay explosion ring.
            angle = point / NOVA_SHELL_POINTS * math.tau
            distance = radius * shell * (1 + math.sin(angle * 5 + phase) * 0.12 + rng.uniform(-0.08, 0.08))
            position = (center[0] + math.cos(angle) * distance,
                        center[1] + math.sin(angle) * distance * 0.8)
            _glow(layer, position, max(1, radius * rng.uniform(0.07, 0.15)), color, NOVA_OPACITY)
    _glow(layer, center, max(2, radius * 0.15), color, NOVA_OPACITY // 2)
    layer = pygame.transform.smoothscale(layer, (layer.get_width() * SOFT_SCALE, layer.get_height() * SOFT_SCALE))
    layer = pygame.transform.rotate(layer, rng.uniform(-45, 45))
    surface.blit(layer, layer.get_rect(center=(round(width * rng.uniform(0.2, 0.8)),
                                              round(height * rng.uniform(0.2, 0.8)))))


STYLE_DRAWERS = {
    "empty": draw_empty, "planet": draw_planet, "galaxy": draw_galaxy,
    "nebula": draw_nebula, "black_hole": draw_black_hole, "nova": draw_nova,
}


def generate_background(seed: int, size: tuple[int, int], style: str | None = None):
    """Return (cached surface, style) using only a private, arena-derived RNG."""
    width, height = size
    if width <= 0 or height <= 0:
        raise ValueError("Background dimensions must be positive")
    if not 0 <= BRIGHTNESS <= 1 or not 0 <= OPACITY <= 1:
        raise ValueError("Background brightness and opacity must be between 0 and 1")
    rng = random.Random(seed ^ SEED_SALT)
    selected = choose_style(rng)  # Consume the draw even for an explicitly forced style.
    style = selected if style is None else style
    if style not in STYLE_DRAWERS:
        raise ValueError(f"Unknown background style: {style}")
    surface = pygame.Surface(size)
    top, bottom = rng.choice(BASE_PALETTES)
    for y in range(height):
        fraction = y / max(1, height - 1)
        color = tuple(round(a + (b - a) * fraction) for a, b in zip(top, bottom))
        pygame.draw.line(surface, color, (0, y), (width - 1, y))
    _stars(surface, rng, style)
    STYLE_DRAWERS[style](surface, rng)
    fade = round(255 * BRIGHTNESS)
    surface.fill((fade, fade, fade), special_flags=pygame.BLEND_RGB_MULT)
    surface.set_alpha(round(255 * OPACITY))
    return surface, style


def save_previews(seeds, output, size, style=None):
    """Save a labelled grid, generating at the real viewport size before scaling."""
    if not seeds:
        raise ValueError("At least one background seed is required")
    pygame.font.init()
    font = pygame.font.Font(None, 24)
    columns = min(4, math.ceil(math.sqrt(len(seeds))))
    rows = math.ceil(len(seeds) / columns)
    tile_width = min(PREVIEW_WIDTH, size[0]) if len(seeds) > 1 else size[0]
    tile_height = round(size[1] * tile_width / size[0])
    sheet = pygame.Surface((columns * (tile_width + PREVIEW_MARGIN) + PREVIEW_MARGIN,
                            rows * (tile_height + PREVIEW_CAPTION + PREVIEW_MARGIN) + PREVIEW_MARGIN))
    sheet.fill((18, 20, 26))
    for index, seed in enumerate(seeds):
        surface, selected = generate_background(seed, size, style)
        x = PREVIEW_MARGIN + index % columns * (tile_width + PREVIEW_MARGIN)
        y = PREVIEW_MARGIN + index // columns * (tile_height + PREVIEW_CAPTION + PREVIEW_MARGIN)
        label = font.render(f"Seed {seed} | {selected.replace('_', ' ')}", True, (200, 205, 215))
        sheet.blit(label, (x, y))
        # Match the game's black underlay when applying the configured opacity.
        tile = pygame.Surface(size)
        tile.fill("black")
        tile.blit(surface, (0, 0))
        sheet.blit(pygame.transform.smoothscale(tile, (tile_width, tile_height)), (x, y + PREVIEW_CAPTION))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(sheet, str(output))


def main():
    from config import HEIGHT, WIDTH

    parser = argparse.ArgumentParser(description=__doc__)
    seeds = parser.add_mutually_exclusive_group()
    seeds.add_argument("--seed", type=int, help="Preview one seed")
    seeds.add_argument("--start", type=int, default=0, help="First seed in a grid")
    parser.add_argument("--count", type=int, help="Grid size (default: 12)")
    parser.add_argument("--style", choices=STYLE_WEIGHTS, help="Force one background style")
    parser.add_argument("--width", type=int, default=WIDTH)
    parser.add_argument("--height", type=int, default=HEIGHT)
    parser.add_argument("--output", type=Path, default=Path("background_previews.png"))
    args = parser.parse_args()
    count = args.count if args.count is not None else (1 if args.seed is not None else 12)
    if count < 1 or args.width < 1 or args.height < 1:
        parser.error("Count and viewport dimensions must be positive")
    if args.seed is not None and count != 1:
        parser.error("Use --start with --count for a grid")
    selected = [args.seed] if args.seed is not None else list(range(args.start, args.start + count))
    save_previews(selected, args.output, (args.width, args.height), args.style)
    print(f"Saved {len(selected)} background(s) to {args.output}")


if __name__ == "__main__":
    main()
