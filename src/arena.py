"""
Arena geometry, separate from the sprites used to display it.

Authors: Irjan Evertsen
"""

from dataclasses import dataclass
import random

import pygame

from config import FUEL_SIZE, HEIGHT, OBSTACLE_SIZE, PLAYER_RADIUS, WIDTH
from src.geometry import circle_intersects_rect


GRID_SIZE = 24
WALL_CLEARANCE = 72
# Leave a ship-width passage plus room for conservative grid cells.
OBSTACLE_CLEARANCE = 2 * PLAYER_RADIUS + 2 * GRID_SIZE
SPAWN_CLEARANCE = 48
FUEL_PLAYER_CLEARANCE = 48
MIN_SPAWN_DISTANCE = WIDTH // 3
MIN_NAVIGABLE_FRACTION = 0.5
MAX_LAYOUT_ATTEMPTS = 20
MAX_OBSTACLE_ATTEMPTS = 100


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


def rectangle_fits(rect: pygame.Rect, obstacles: list[pygame.Rect]) -> bool:
    """Check bounds and overlaps, without making any reachability guarantee."""
    return (
        rect.width > 0
        and rect.height > 0
        and rect.left >= 0
        and rect.top >= 0
        and rect.right <= WIDTH
        and rect.bottom <= HEIGHT
        and not any(rect.colliderect(obstacle) for obstacle in obstacles)
    )


def _obstacle_fits(rect, obstacles, spawns) -> bool:
    """Keep passages between obstacles, walls and the reserved spawn areas."""
    interior = pygame.Rect(
        WALL_CLEARANCE, WALL_CLEARANCE,
        WIDTH - 2 * WALL_CLEARANCE, HEIGHT - 2 * WALL_CLEARANCE,
    )
    if rect.width <= 0 or rect.height <= 0 or not interior.contains(rect):
        return False

    spaced_rect = rect.inflate(2 * OBSTACLE_CLEARANCE, 2 * OBSTACLE_CLEARANCE)
    if any(spaced_rect.colliderect(other) for other in obstacles):
        return False

    return not any(
        circle_intersects_rect(spawn, PLAYER_RADIUS + SPAWN_CLEARANCE, rect)
        for spawn in spawns
    )


def get_reachable_cells(arena: ArenaLayout) -> set[tuple[int, int]]:
    """Return (column, row) grid cells reachable from player one's spawn."""
    open_cells = set()
    for column in range(WIDTH // GRID_SIZE):
        for row in range(HEIGHT // GRID_SIZE):
            cell = pygame.Rect(
                column * GRID_SIZE, row * GRID_SIZE, GRID_SIZE, GRID_SIZE,
            )
            # Check the whole cell plus the ship radius, not just its center.
            # This conservatively guarantees safe movement inside each cell
            # and across shared edges, even past very thin obstacles.
            footprint = cell.inflate(2 * PLAYER_RADIUS, 2 * PLAYER_RADIUS)
            if rectangle_fits(footprint, arena.obstacles):
                open_cells.add((column, row))

    start = (
        arena.player1_spawn[0] // GRID_SIZE,
        arena.player1_spawn[1] // GRID_SIZE,
    )
    if start not in open_cells:
        return set()

    reachable = {start}
    pending = [start]
    while pending:
        column, row = pending.pop()
        for neighbor in (
            (column - 1, row), (column + 1, row),
            (column, row - 1), (column, row + 1),
        ):
            if neighbor in open_cells and neighbor not in reachable:
                reachable.add(neighbor)
                pending.append(neighbor)

    return reachable


def validate_arena(arena: ArenaLayout) -> bool:
    """Check clearances, safe spawns and a large connected playable region.

    Obstacle count and size ranges are generation choices; the original
    one-obstacle fallback is checked against the same safety rules.
    """
    spawns = (arena.player1_spawn, arena.player2_spawn)
    spawn_margin = PLAYER_RADIUS + SPAWN_CLEARANCE
    for x, y in spawns:
        if not (spawn_margin <= x <= WIDTH - spawn_margin
                and spawn_margin <= y <= HEIGHT - spawn_margin):
            return False

    dx = spawns[0][0] - spawns[1][0]
    dy = spawns[0][1] - spawns[1][1]
    if dx * dx + dy * dy < MIN_SPAWN_DISTANCE ** 2:
        return False

    for index, obstacle in enumerate(arena.obstacles):
        if not _obstacle_fits(obstacle, arena.obstacles[:index], spawns):
            return False

    reachable = get_reachable_cells(arena)
    second_spawn_cell = (
        arena.player2_spawn[0] // GRID_SIZE,
        arena.player2_spawn[1] // GRID_SIZE,
    )
    total_cells = (WIDTH // GRID_SIZE) * (HEIGHT // GRID_SIZE)
    # A shared tiny pocket is connected, but does not make a useful arena.
    return (
        second_spawn_cell in reachable
        and len(reachable) >= total_cells * MIN_NAVIGABLE_FRACTION
    )


def generate_arena(seed: int) -> ArenaLayout:
    """Generate a repeatable layout, or return the validated original room."""
    rng = random.Random(seed)
    spawn_margin = PLAYER_RADIUS + SPAWN_CLEARANCE

    for _ in range(MAX_LAYOUT_ATTEMPTS):
        # Opposite thirds keep players separated without fixing their positions.
        player1_spawn = (
            rng.randint(spawn_margin, WIDTH // 3),
            rng.randint(spawn_margin, HEIGHT - spawn_margin),
        )
        player2_spawn = (
            rng.randint(WIDTH * 2 // 3, WIDTH - spawn_margin),
            rng.randint(spawn_margin, HEIGHT - spawn_margin),
        )
        spawns = (player1_spawn, player2_spawn)
        obstacle_count = rng.randint(2, 6)
        obstacles = []

        for _ in range(MAX_OBSTACLE_ATTEMPTS):
            width = rng.randint(80, 180)
            height = rng.randint(60, 160)
            rect = pygame.Rect(
                rng.randint(WALL_CLEARANCE, WIDTH - WALL_CLEARANCE - width),
                rng.randint(WALL_CLEARANCE, HEIGHT - WALL_CLEARANCE - height),
                width, height,
            )
            if _obstacle_fits(rect, obstacles, spawns):
                obstacles.append(rect)
                if len(obstacles) == obstacle_count:
                    break

        if len(obstacles) != obstacle_count:
            continue

        arena = ArenaLayout(obstacles, player1_spawn, player2_spawn)
        if validate_arena(arena):
            return arena

    fallback = create_fixed_arena()
    if not validate_arena(fallback):
        raise RuntimeError('Arena generation failed and the fixed fallback is invalid.')
    return fallback


def get_fuel_positions(arena: ArenaLayout) -> list[tuple[int, int]]:
    """Return fuel top-left positions whose centers are reachable by a ship."""
    positions = []
    # Sorting makes fuel choices reproducible, independent of set iteration order.
    for column, row in sorted(get_reachable_cells(arena)):
        rect = pygame.Rect((0, 0), FUEL_SIZE)
        rect.center = (
            column * GRID_SIZE + GRID_SIZE // 2,
            row * GRID_SIZE + GRID_SIZE // 2,
        )
        # Fuel is wider than a grid cell, so checking only its center is not enough.
        if rectangle_fits(rect, arena.obstacles):
            positions.append(rect.topleft)
    return positions


def choose_fuel_position(positions, player_positions, rng) -> tuple[int, int] | None:
    """Choose from prevalidated positions, leaving space around current players."""
    available = []
    for position in positions:
        rect = pygame.Rect(position, FUEL_SIZE)
        if not any(
            circle_intersects_rect(player, PLAYER_RADIUS + FUEL_PLAYER_CLEARANCE, rect)
            for player in player_positions
        ):
            available.append(position)
    return rng.choice(available) if available else None
