"""Save arena previews without creating a game or opening a window."""

import argparse
import math
from pathlib import Path

import pygame

from config import DESTRUCTIBLE_COLOR, HEIGHT, OBSTACLE_COLOR, PLAYER_RADIUS, WIDTH
from src.arena import ARENA_STYLES, generate_arena
from src.objects import draw_hazard


def save_previews(seeds: list[int], output: Path, style: str | None = None) -> None:
    """Draw arenas at their real dimensions, then arrange them in a PNG."""
    if not seeds:
        raise ValueError("At least one seed is required")

    pygame.font.init()
    font = pygame.font.Font(None, 28)
    columns = min(4, math.ceil(math.sqrt(len(seeds))))
    rows = math.ceil(len(seeds) / columns)
    # Several full-size arenas would make an unwieldy image. Only thumbnails
    # are scaled; generation and drawing always use the actual world geometry.
    tile_size = (WIDTH, HEIGHT) if len(seeds) == 1 else (WIDTH // 2, HEIGHT // 2)
    margin = 12
    caption_height = 36
    tile_width, tile_height = tile_size
    sheet = pygame.Surface((
        columns * (tile_width + margin) + margin,
        rows * (tile_height + caption_height + margin) + margin + 28,
    ))
    sheet.fill((30, 30, 30))

    for index, seed in enumerate(seeds):
        arena = generate_arena(seed, style)
        room = pygame.Surface((WIDTH, HEIGHT))
        room.fill("black")
        for rect in arena.obstacles:
            color = DESTRUCTIBLE_COLOR if rect in arena.destructible_obstacles else OBSTACLE_COLOR
            pygame.draw.rect(room, color, rect)
        for rect in arena.hazards:
            draw_hazard(room, rect)
        pygame.draw.circle(room, "dodgerblue", arena.player1_spawn, PLAYER_RADIUS)
        pygame.draw.circle(room, "red", arena.player2_spawn, PLAYER_RADIUS)

        x = margin + (index % columns) * (tile_width + margin)
        y = margin + (index // columns) * (tile_height + caption_height + margin)
        caption = font.render(f"Seed {seed}  |  {arena.style}", True, "white")
        sheet.blit(caption, (x, y))
        sheet.blit(pygame.transform.smoothscale(room, tile_size), (x, y + caption_height))

    legend_font = pygame.font.Font(None, 22)
    legend = legend_font.render(
        "White: solid | Tan: 3-hit blocks | Red spikes: lethal | Blue/red dots: P1/P2",
        True, "white",
    )
    sheet.blit(legend, (margin, sheet.get_height() - 26))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(sheet, str(output))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    seeds = parser.add_mutually_exclusive_group()
    seeds.add_argument("--seed", type=int, help="Preview one arena")
    seeds.add_argument("--start", type=int, default=0, help="First seed in a sequence")
    parser.add_argument("--count", type=int, default=1, help="Number of consecutive seeds")
    parser.add_argument("--output", type=Path, default=Path("arena_previews.png"))
    parser.add_argument("--style", choices=ARENA_STYLES, help="Preview a specific room style")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.seed is not None and args.count != 1:
        parser.error("Use --start with --count to preview several arenas")

    selected = [args.seed] if args.seed is not None else list(range(args.start, args.start + args.count))
    save_previews(selected, args.output, args.style)
    print(f"Saved {len(selected)} arena preview(s) to {args.output}")


if __name__ == "__main__":
    main()
