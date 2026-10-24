"""
Arena geometry, separate from the sprites used to display it.

Authors: Irjan Evertsen
"""

from dataclasses import dataclass, field
import random

import pygame # type: ignore

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
ARENA_STYLES = ("open", "corridors", "scattered")
STYLE_CLEARANCE = {"fixed": OBSTACLE_CLEARANCE, "open": 100, "corridors": 60, "scattered": 60}
HAZARD_CLEARANCE = 40


@dataclass
class ArenaLayout:
    """Obstacle rectangles and player center positions for one round."""

    obstacles: list[pygame.Rect]
    player1_spawn: tuple[int, int]
    player2_spawn: tuple[int, int]
    style: str = "fixed"
    # These are the same rectangles as obstacles, grouped in connected order.
    # The flat list keeps collision code independent of the structure shapes.
    structures: list[list[pygame.Rect]] = field(default_factory=list)
    hazards: list[pygame.Rect] = field(default_factory=list)
    destructible_obstacles: list[pygame.Rect] = field(default_factory=list)


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


def _obstacle_fits(rect, obstacles, spawns, clearance=OBSTACLE_CLEARANCE) -> bool:
    """Keep passages between obstacles, walls and the reserved spawn areas."""
    interior = pygame.Rect(
        WALL_CLEARANCE, WALL_CLEARANCE,
        WIDTH - 2 * WALL_CLEARANCE, HEIGHT - 2 * WALL_CLEARANCE,
    )
    if rect.width <= 0 or rect.height <= 0 or not interior.contains(rect):
        return False

    spaced_rect = rect.inflate(2 * clearance, 2 * clearance)
    if any(spaced_rect.colliderect(other) for other in obstacles):
        return False

    return not any(
        circle_intersects_rect(spawn, PLAYER_RADIUS + SPAWN_CLEARANCE, rect)
        for spawn in spawns
    )


def _structure_fits(rects, obstacles, spawns, clearance) -> bool:
    """Allow touching parts inside a structure, but keep separate structures apart."""
    if not rects:
        return False
    for index, rect in enumerate(rects):
        if not _obstacle_fits(rect, obstacles, spawns, clearance):
            return False
        if any(rect.colliderect(other) for other in rects[:index]):
            return False
        # Parts are listed in connected order. One pixel of expansion detects
        # touching edges without treating a one-pixel gap as connected.
        if index and not any(rect.inflate(2, 2).colliderect(other) for other in rects[:index]):
            return False
    return True


def get_reachable_cells(arena: ArenaLayout, obstacles=None) -> set[tuple[int, int]]:
    """Return safe grid cells; optional live obstacles account for destroyed blocks."""
    if obstacles is None:
        obstacles = arena.obstacles
    blocked = obstacles + arena.hazards
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
            if rectangle_fits(footprint, blocked):
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

    if arena.style not in STYLE_CLEARANCE:
        return False
    structures = arena.structures or [[rect] for rect in arena.obstacles]
    if [rect for structure in structures for rect in structure] != arena.obstacles:
        return False
    placed = []
    for structure in structures:
        if not _structure_fits(structure, placed, spawns, STYLE_CLEARANCE[arena.style]):
            return False
        placed.extend(structure)
    if any(rect not in arena.obstacles for rect in arena.destructible_obstacles):
        return False
    for hazard in arena.hazards:
        if not _obstacle_fits(hazard, placed, spawns, HAZARD_CLEARANCE):
            return False
        placed.append(hazard)

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


def _rotate_structure(parts, quarter_turns) -> list[pygame.Rect]:
    """Turn local rectangles clockwise, keeping their shared edges and origin."""
    for _ in range(quarter_turns):
        height = max(rect.bottom for rect in parts)
        parts = [pygame.Rect(height - rect.bottom, rect.x, rect.height, rect.width)
                 for rect in parts]
    return parts


def _make_structure(rng, style, vertical_lanes=True) -> list[pygame.Rect]:
    """Build a block, L or U using touching, non-overlapping rectangles."""
    if style == "corridors":
        height = rng.randint(280, 380)
        width = rng.randint(112, 140)
        thickness = rng.randint(24, 32)
        shape = rng.choice(("block", "L", "U"))
        if not vertical_lanes:
            width, height = height, width
    else:
        width = rng.randint(120, 180)
        height = rng.randint(100, 170)
        thickness = rng.randint(24, 32)
        shapes = ("block", "block", "block", "L") if style == "open" else ("block", "block", "L")
        shape = rng.choice(shapes)
    if shape == "block":
        if style == "corridors":
            size = (thickness, height) if vertical_lanes else (width, thickness)
            return [pygame.Rect(0, 0, *size)]
        if style == "open":
            width, height = rng.randint(80, 140), rng.randint(60, 120)
        else:
            width, height = rng.randint(60, 100), rng.randint(50, 100)
        return [pygame.Rect(0, 0, width, height)]

    quarter_turns = rng.choice((0, 1, 2, 3))
    if style == "corridors" and quarter_turns % 2:
        # Keep the final long axis along its lane for every orientation. Otherwise
        # sideways structures are rejected much more often in the narrow lanes.
        width, height = height, width
    parts = [
        pygame.Rect(0, 0, thickness, height),
        pygame.Rect(thickness, height - thickness, width - thickness, thickness),
    ]
    if shape == "U":
        # Shorten the bottom so the right-hand side only touches it.
        parts[1].width -= thickness
        parts.append(pygame.Rect(width - thickness, 0, thickness, height))
    return _rotate_structure(parts, quarter_turns)


def generate_arena(seed: int, style: str | None = None) -> ArenaLayout:
    """Generate a repeatable room style, or return the validated original room."""
    rng = random.Random(seed)
    # Always consume the style draw, so explicitly choosing the reported style
    # reproduces the automatic layout for the same seed.
    random_style = rng.choice(ARENA_STYLES)
    style = random_style if style is None else style
    if style not in ARENA_STYLES:
        raise ValueError(f"Unknown arena style: {style}")
    spawn_margin = PLAYER_RADIUS + SPAWN_CLEARANCE

    for _ in range(MAX_LAYOUT_ATTEMPTS):
        spawns = (
            (rng.randint(spawn_margin, WIDTH // 3),
             rng.randint(spawn_margin, HEIGHT - spawn_margin)),
            (rng.randint(WIDTH * 2 // 3, WIDTH - spawn_margin),
             rng.randint(spawn_margin, HEIGHT - spawn_margin)),
        )
        if style == "open":
            structure_count = rng.randint(2, 3)
        elif style == "corridors":
            structure_count = 3
        else:
            structure_count = rng.randint(5, 7)
        vertical_lanes = rng.choice((True, False))
        structures = []
        obstacles = []

        for _ in range(MAX_OBSTACLE_ATTEMPTS):
            parts = _make_structure(rng, style, vertical_lanes)
            bounds = parts[0].unionall(parts[1:])
            if style == "corridors":
                # Alternating long walls leave openings at opposite ends.
                index = len(structures)
                if vertical_lanes:
                    x = (index + 1) * WIDTH // 4 - bounds.width // 2 + rng.randint(-16, 16)
                    y = WALL_CLEARANCE if index % 2 == 0 else HEIGHT - WALL_CLEARANCE - bounds.height
                else:
                    x = WALL_CLEARANCE if index % 2 == 0 else WIDTH - WALL_CLEARANCE - bounds.width
                    y = (index + 1) * HEIGHT // 4 - bounds.height // 2 + rng.randint(-8, 8)
            else:
                x = rng.randint(WALL_CLEARANCE, WIDTH - WALL_CLEARANCE - bounds.width)
                y = rng.randint(WALL_CLEARANCE, HEIGHT - WALL_CLEARANCE - bounds.height)
            parts = [rect.move(x, y) for rect in parts]
            if _structure_fits(parts, obstacles, spawns, STYLE_CLEARANCE[style]):
                structures.append(parts)
                obstacles.extend(parts)
                if len(structures) == structure_count:
                    break
        if len(structures) != structure_count:
            continue

        hazards = []
        if rng.random() < 0.35:
            hazard_count = rng.randint(1, 2)
            for _ in range(40):
                width = rng.randint(80, 160)
                hazard = pygame.Rect(
                    rng.randint(WALL_CLEARANCE, WIDTH - WALL_CLEARANCE - width),
                    rng.randint(WALL_CLEARANCE, HEIGHT - WALL_CLEARANCE - 32), width, 32,
                )
                if _obstacle_fits(hazard, obstacles + hazards, spawns, HAZARD_CLEARANCE):
                    hazards.append(hazard)
                    if len(hazards) == hazard_count:
                        break
        destructible = []
        for structure in structures:
            if rng.random() < 0.35:
                destructible.extend(structure)
        arena = ArenaLayout(
            obstacles=obstacles,
            player1_spawn=spawns[0],
            player2_spawn=spawns[1],
            style=style,
            structures=structures,
            hazards=hazards,
            destructible_obstacles=destructible,
        )
        if validate_arena(arena):
            return arena

    fallback = create_fixed_arena()
    if not validate_arena(fallback):
        raise RuntimeError('Arena generation failed and the fixed fallback is invalid.')
    return fallback


def get_fuel_positions(arena: ArenaLayout, obstacles=None) -> list[tuple[int, int]]:
    """Return fuel top-left positions whose centers are reachable by a ship."""
    if obstacles is None:
        obstacles = arena.obstacles
    blocked = obstacles + arena.hazards
    positions = []
    # Sorting makes fuel choices reproducible, independent of set iteration order.
    for column, row in sorted(get_reachable_cells(arena, obstacles)):
        rect = pygame.Rect((0, 0), FUEL_SIZE)
        rect.center = (
            column * GRID_SIZE + GRID_SIZE // 2,
            row * GRID_SIZE + GRID_SIZE // 2,
        )
        # Fuel is wider than a grid cell, so checking only its center is not enough.
        if rectangle_fits(rect, blocked):
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
