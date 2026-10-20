"""Tests for fixed and procedurally generated arena geometry."""

from collections import Counter
import random
import unittest
from unittest.mock import patch

import pygame

from config import FUEL_SIZE, HEIGHT, PLAYER_RADIUS, WIDTH
from src.arena import (
    ARENA_STYLES, STYLE_CLEARANCE, GRID_SIZE, MIN_NAVIGABLE_FRACTION, MIN_SPAWN_DISTANCE,
    OBSTACLE_CLEARANCE, SPAWN_CLEARANCE, WALL_CLEARANCE,
    ArenaLayout, _make_structure, _rotate_structure, create_fixed_arena, generate_arena,
    get_fuel_positions, get_reachable_cells,
    rectangle_fits, validate_arena,
)
from src.geometry import circle_intersects_rect
from src.objects import Obstacle
from src.player import Player1


class FixedArenaTests(unittest.TestCase):
    def test_obstacle_position_and_size(self):
        arena = create_fixed_arena()

        self.assertEqual(arena.obstacles, [pygame.Rect(460, 280, 160, 160)])

    def test_player_spawn_positions(self):
        arena = create_fixed_arena()

        self.assertEqual(arena.player1_spawn, (270, 180))
        self.assertEqual(arena.player2_spawn, (810, 540))

    def test_layouts_do_not_share_mutable_obstacles(self):
        first_arena = create_fixed_arena()
        second_arena = create_fixed_arena()

        first_arena.obstacles[0].move_ip(10, 20)
        first_arena.obstacles.clear()

        self.assertEqual(second_arena.obstacles, [pygame.Rect(460, 280, 160, 160)])


class GeneratedArenaTests(unittest.TestCase):
    def test_same_seed_produces_identical_layouts(self):
        for seed in (0, 1, 42, -17):
            with self.subTest(seed=seed):
                self.assertEqual(generate_arena(seed), generate_arena(seed))

    def test_different_seeds_produce_variation(self):
        arenas = [generate_arena(seed) for seed in range(5)]

        self.assertTrue(any(arena != arenas[0] for arena in arenas[1:]))
        sizes = {rect.size for arena in arenas for rect in arena.obstacles}
        self.assertGreater(len(sizes), 1)

    def test_generation_leaves_global_random_state_unchanged(self):
        state = random.getstate()

        generate_arena(42)

        self.assertEqual(random.getstate(), state)

    def test_failed_placement_attempts_return_valid_fixed_arena(self):
        # One candidate cannot fill any style, which needs at least two structures.
        with patch('src.arena.MAX_OBSTACLE_ATTEMPTS', 1):
            arena = generate_arena(42)

        self.assertEqual(arena, create_fixed_arena())
        self.assertTrue(validate_arena(arena))

    def test_invalid_fallback_is_not_returned(self):
        invalid_fallback = create_fixed_arena()
        invalid_fallback.player1_spawn = (-10, -10)
        with patch('src.arena.MAX_LAYOUT_ATTEMPTS', 0):
            with patch('src.arena.create_fixed_arena', return_value=invalid_fallback):
                with self.assertRaisesRegex(RuntimeError, 'fallback is invalid'):
                    generate_arena(42)

    def test_fixed_arena_is_valid_under_safety_rules(self):
        self.assertTrue(validate_arena(create_fixed_arena()))

    def test_500_seeds_produce_safe_playable_arenas(self):
        fallback = create_fixed_arena()
        fallback_count = 0
        bounds = pygame.Rect(0, 0, WIDTH, HEIGHT)
        spawn_margin = PLAYER_RADIUS + SPAWN_CLEARANCE

        for seed in range(500):
            with self.subTest(seed=seed):
                arena = generate_arena(seed)
                self.assertTrue(validate_arena(arena))
                if arena == fallback:
                    fallback_count += 1
                else:
                    self.assertIn(arena.style, ARENA_STYLES)
                    self.assertGreaterEqual(len(arena.structures), 2)
                    self.assertLessEqual(len(arena.structures), 7)
                    self.assertLessEqual(arena.player1_spawn[0], WIDTH // 3)
                    self.assertGreaterEqual(arena.player2_spawn[0], WIDTH * 2 // 3)

                for index, rect in enumerate(arena.obstacles):
                    self.assertTrue(bounds.contains(rect))
                    self.assertGreaterEqual(rect.left, WALL_CLEARANCE)
                    self.assertGreaterEqual(rect.top, WALL_CLEARANCE)
                    self.assertGreaterEqual(WIDTH - rect.right, WALL_CLEARANCE)
                    self.assertGreaterEqual(HEIGHT - rect.bottom, WALL_CLEARANCE)
                    for other in arena.obstacles[index + 1:]:
                        self.assertFalse(rect.colliderect(other))
                structures = arena.structures or [[rect] for rect in arena.obstacles]
                for index, structure in enumerate(structures):
                    for other_structure in structures[index + 1:]:
                        for rect in structure:
                            spaced = rect.inflate(2 * STYLE_CLEARANCE[arena.style],
                                                  2 * STYLE_CLEARANCE[arena.style])
                            for other in other_structure:
                                self.assertFalse(spaced.colliderect(other))
                for index, hazard in enumerate(arena.hazards):
                    self.assertTrue(rectangle_fits(hazard, arena.obstacles + arena.hazards[:index]))

                for spawn in (arena.player1_spawn, arena.player2_spawn):
                    x, y = spawn
                    self.assertGreaterEqual(x, spawn_margin)
                    self.assertGreaterEqual(y, spawn_margin)
                    self.assertLessEqual(x, WIDTH - spawn_margin)
                    self.assertLessEqual(y, HEIGHT - spawn_margin)
                    player = Player1(x, y)
                    self.assertEqual(player.radius, PLAYER_RADIUS)
                    for hazard in arena.hazards:
                        self.assertFalse(circle_intersects_rect(spawn, spawn_margin, hazard))
                    for rect in arena.obstacles:
                        obstacle = Obstacle(rect.x, rect.y, rect.size, 'white')
                        self.assertFalse(player.collision(obstacle))
                        self.assertFalse(circle_intersects_rect(spawn, spawn_margin, rect))

                dx = arena.player1_spawn[0] - arena.player2_spawn[0]
                dy = arena.player1_spawn[1] - arena.player2_spawn[1]
                self.assertGreaterEqual(dx * dx + dy * dy, MIN_SPAWN_DISTANCE ** 2)
                reachable = get_reachable_cells(arena)
                for x, y in (arena.player1_spawn, arena.player2_spawn):
                    self.assertIn((x // GRID_SIZE, y // GRID_SIZE), reachable)
                total_cells = (WIDTH // GRID_SIZE) * (HEIGHT // GRID_SIZE)
                self.assertGreaterEqual(len(reachable), total_cells * MIN_NAVIGABLE_FRACTION)

        print(f'\nSeed sweep: {fallback_count}/500 fixed-layout fallbacks.')
        # A few exceptional seeds are acceptable; frequent fallback needs tuning.
        self.assertLessEqual(fallback_count, 5)


class RichArenaTests(unittest.TestCase):
    def assert_structure_geometry(self, parts):
        """Check solid edge joins and identify the L's missing corner or U's mouth."""
        bounds = parts[0].unionall(parts[1:])
        for index, rect in enumerate(parts):
            self.assertGreater(rect.width, 0)
            self.assertGreater(rect.height, 0)
            self.assertTrue(bounds.contains(rect))
            for other in parts[:index]:
                self.assertFalse(rect.colliderect(other))
            if index:
                self.assertTrue(any(
                    ((rect.right == other.left or rect.left == other.right)
                     and min(rect.bottom, other.bottom) > max(rect.top, other.top))
                    or ((rect.bottom == other.top or rect.top == other.bottom)
                        and min(rect.right, other.right) > max(rect.left, other.left))
                    for other in parts[:index]
                ))
        if len(parts) == 1:
            return None
        corners = (
            (bounds.right - 1, bounds.top), (bounds.right - 1, bounds.bottom - 1),
            (bounds.left, bounds.bottom - 1), (bounds.left, bounds.top),
        )
        if len(parts) == 2:
            points = corners
        else:
            self.assertEqual(len(parts), 3)
            self.assertTrue(all(any(rect.collidepoint(point) for rect in parts) for point in corners))
            points = (
                (bounds.centerx, bounds.top), (bounds.right - 1, bounds.centery),
                (bounds.centerx, bounds.bottom - 1), (bounds.left, bounds.centery),
            )
        covered = [any(rect.collidepoint(point) for rect in parts) for point in points]
        self.assertEqual(covered.count(False), 1)
        return covered.index(False)

    def test_l_and_u_quarter_turns_have_exact_geometry(self):
        left = (0, 0, 24, 100)
        shapes = (
            ([left, (24, 76, 136, 24)], (
                [left, (24, 76, 136, 24)],
                [(0, 0, 100, 24), (0, 24, 24, 136)],
                [(136, 0, 24, 100), (0, 0, 136, 24)],
                [(0, 136, 100, 24), (76, 0, 24, 136)],
            )),
            ([left, (24, 76, 112, 24), (136, 0, 24, 100)], (
                [left, (24, 76, 112, 24), (136, 0, 24, 100)],
                [(0, 0, 100, 24), (0, 24, 24, 112), (0, 136, 100, 24)],
                [(136, 0, 24, 100), (24, 0, 112, 24), (0, 0, 24, 100)],
                [(0, 136, 100, 24), (76, 24, 24, 112), (0, 0, 100, 24)],
            )),
        )
        for original, orientations in shapes:
            parts = [pygame.Rect(rect) for rect in original]
            for turn, expected in enumerate(orientations):
                with self.subTest(parts=len(parts), turn=turn):
                    rotated = _rotate_structure(parts, turn)
                    self.assertEqual(rotated, [pygame.Rect(rect) for rect in expected])
                    self.assertEqual(self.assert_structure_geometry(rotated), turn)
                    self.assertEqual(sum(rect.width * rect.height for rect in rotated),
                                     sum(rect.width * rect.height for rect in parts))
                    self.assertEqual(parts, [pygame.Rect(rect) for rect in original])
            self.assertEqual(_rotate_structure(parts, 4), parts)

    def test_corridor_orientations_keep_the_same_lane_dimensions(self):
        for vertical in (True, False):
            for shape in ("L", "U"):
                sizes = []
                for turn in range(4):
                    rng = random.Random(42)
                    with patch.object(rng, 'choice', side_effect=(shape, turn)):
                        parts = _make_structure(rng, "corridors", vertical)
                    self.assertEqual(self.assert_structure_geometry(parts), turn)
                    bounds = parts[0].unionall(parts[1:])
                    sizes.append(bounds.size)
                    self.assertEqual(bounds.topleft, (0, 0))
                    self.assertGreaterEqual(max(bounds.size), 280)
                    self.assertEqual(bounds.height > bounds.width, vertical)
                self.assertEqual(len(set(sizes)), 1)

    def test_each_style_is_valid_repeatable_and_varied_for_300_seeds(self):
        for style in ARENA_STYLES:
            fallback_count = 0
            shapes = Counter()
            orientations = {2: Counter(), 3: Counter()}
            sizes = {2: set(), 3: set()}
            for seed in range(300):
                with self.subTest(style=style, seed=seed):
                    arena = generate_arena(seed, style)
                    self.assertEqual(arena, generate_arena(seed, style))
                    self.assertTrue(validate_arena(arena))
                    if arena.style == "fixed":
                        fallback_count += 1
                    else:
                        self.assertEqual(arena.style, style)
                        if style == "open":
                            self.assertLessEqual(len(arena.structures), 3)
                        elif style == "corridors":
                            self.assertEqual(len(arena.structures), 3)
                            self.assertTrue(all(max(group[0].unionall(group[1:]).size) >= 280
                                                for group in arena.structures))
                        else:
                            self.assertGreaterEqual(len(arena.structures), 5)
                    for group in arena.structures:
                        shapes[len(group)] += 1
                        turn = self.assert_structure_geometry(group)
                        if turn is not None:
                            orientations[len(group)][turn] += 1
                            sizes[len(group)].add(group[0].unionall(group[1:]).size)
                    positions = get_fuel_positions(arena)
                    self.assertTrue(positions)
                    reachable = get_reachable_cells(arena)
                    for position in positions:
                        fuel = pygame.Rect(position, FUEL_SIZE)
                        self.assertTrue(rectangle_fits(fuel, arena.obstacles + arena.hazards))
                        self.assertIn((fuel.centerx // GRID_SIZE, fuel.centery // GRID_SIZE), reachable)
            expected_shapes = (2, 3) if style == "corridors" else (2,)
            for shape in expected_shapes:
                counts = orientations[shape]
                self.assertEqual(set(counts), set(range(4)))
                self.assertGreater(len(sizes[shape]), 10)
                for count in counts.values():
                    # Broad bounds catch systematic rejection bias, not minor
                    # differences from uniformly random sampling and placement.
                    self.assertGreaterEqual(count, sum(counts.values()) * 0.15)
                    self.assertLessEqual(count, sum(counts.values()) * 0.35)
            if style != "corridors":
                self.assertGreater(shapes[1], sum(shapes.values()) * 0.6)
                self.assertEqual(shapes[3], 0)
            print(f"{style}: {fallback_count}/300 fallbacks; "
                  f"L orientations: {dict(orientations[2])}; U orientations: {dict(orientations[3])}")
            self.assertLessEqual(fallback_count, 3)

    def test_styles_have_grouped_shapes_and_optional_environment_features(self):
        arenas = [generate_arena(seed) for seed in range(40)]
        self.assertEqual({arena.style for arena in arenas}, set(ARENA_STYLES))
        self.assertTrue(any(any(len(group) == 2 for group in arena.structures) for arena in arenas))
        self.assertTrue(any(any(len(group) == 3 for group in arena.structures) for arena in arenas))
        self.assertTrue(any(arena.hazards for arena in arenas))
        self.assertTrue(any(not arena.hazards for arena in arenas))
        self.assertTrue(any(arena.destructible_obstacles for arena in arenas))
        self.assertTrue(any(not arena.destructible_obstacles for arena in arenas))
        for seed, arena in enumerate(arenas):
            self.assertEqual(arena, generate_arena(seed, arena.style))
            self.assertEqual([rect for group in arena.structures for rect in group], arena.obstacles)
            self.assertTrue(all(rect in arena.obstacles for rect in arena.destructible_obstacles))

    def test_touching_l_and_u_structures_are_valid(self):
        left = pygame.Rect(400, 260, 32, 160)
        bottom = pygame.Rect(432, 388, 128, 32)
        parts = [left, bottom]
        arena = ArenaLayout(parts, (270, 180), (810, 540), structures=[parts])
        self.assertTrue(validate_arena(arena))
        bottom.width = 96
        parts.append(pygame.Rect(528, 260, 32, 160))
        self.assertTrue(validate_arena(arena))

    def test_invalid_group_and_destructible_metadata_is_rejected(self):
        first = pygame.Rect(350, 260, 32, 160)
        second = pygame.Rect(700, 260, 32, 160)
        arena = ArenaLayout([first, second], (270, 180), (900, 540), structures=[[first, second]])
        self.assertFalse(validate_arena(arena))
        arena = create_fixed_arena()
        arena.structures = [[first]]
        self.assertFalse(validate_arena(arena))
        arena.structures = []
        arena.destructible_obstacles = [first]
        self.assertFalse(validate_arena(arena))

    def test_invalid_hazards_are_rejected(self):
        for hazard in (pygame.Rect(-1, 200, 80, 32), pygame.Rect(480, 300, 80, 32),
                       pygame.Rect(250, 170, 80, 32)):
            with self.subTest(hazard=hazard):
                arena = create_fixed_arena()
                arena.hazards = [hazard]
                self.assertFalse(validate_arena(arena))

    def test_hazards_block_connectivity_and_fuel_candidates(self):
        arena = ArenaLayout([], (120, 360), (960, 360),
                            hazards=[pygame.Rect(WIDTH // 2, 0, 20, HEIGHT)])
        reachable = get_reachable_cells(arena)
        self.assertNotIn((960 // GRID_SIZE, 360 // GRID_SIZE), reachable)

    def test_unknown_style_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_arena(42, "unknown")


class ArenaValidationTests(unittest.TestCase):
    def test_rejects_overlapping_obstacles(self):
        arena = create_fixed_arena()
        arena.obstacles.append(arena.obstacles[0].copy())

        self.assertFalse(validate_arena(arena))

    def test_rejects_obstacles_too_close_to_each_other(self):
        arena = create_fixed_arena()
        first = pygame.Rect(380, 280, 80, 80)
        second = pygame.Rect(first.right + OBSTACLE_CLEARANCE - 1, 280, 80, 80)
        arena.obstacles = [first, second]

        self.assertFalse(validate_arena(arena))

    def test_rejects_obstacles_too_close_to_boundary(self):
        arena = create_fixed_arena()
        arena.obstacles = [pygame.Rect(WALL_CLEARANCE - 1, 280, 80, 80)]

        self.assertFalse(validate_arena(arena))

    def test_rejects_out_of_bounds_or_empty_obstacles(self):
        for rect in (pygame.Rect(-10, 280, 80, 80), pygame.Rect(400, 280, 0, 80)):
            with self.subTest(rect=rect):
                arena = create_fixed_arena()
                arena.obstacles = [rect]
                self.assertFalse(validate_arena(arena))

    def test_rejects_unsafe_or_insufficiently_separated_spawns(self):
        for spawn in ((-10, 180), (PLAYER_RADIUS, 180), (500, 350), (800, 530)):
            with self.subTest(spawn=spawn):
                arena = create_fixed_arena()
                arena.player1_spawn = spawn
                self.assertFalse(validate_arena(arena))

    def test_rejects_connected_but_insufficient_playable_space(self):
        arena = ArenaLayout(
            obstacles=[pygame.Rect(132, 72, WIDTH - 264, HEIGHT - 144)],
            player1_spawn=(66, HEIGHT // 2),
            player2_spawn=(WIDTH - 66, HEIGHT // 2),
        )
        reachable = get_reachable_cells(arena)
        x, y = arena.player2_spawn
        self.assertIn((x // GRID_SIZE, y // GRID_SIZE), reachable)
        self.assertFalse(validate_arena(arena))

    def test_rectangle_fit_checks_full_size_bounds_and_obstacles(self):
        obstacles = [pygame.Rect(100, 100, 80, 80)]

        self.assertTrue(rectangle_fits(pygame.Rect(40, 100, 30, 30), obstacles))
        self.assertTrue(rectangle_fits(pygame.Rect(70, 100, 30, 30), obstacles))
        self.assertFalse(rectangle_fits(pygame.Rect(80, 100, 30, 30), obstacles))
        self.assertFalse(rectangle_fits(pygame.Rect(WIDTH - 10, 0, 30, 30), obstacles))
        self.assertFalse(rectangle_fits(pygame.Rect(0, 0, 0, 30), obstacles))


class ConnectivityTests(unittest.TestCase):
    def test_thin_solid_wall_disconnects_spawns(self):
        arena = ArenaLayout(
            obstacles=[pygame.Rect(WIDTH // 2, 0, 1, HEIGHT)],
            player1_spawn=(120, 360),
            player2_spawn=(960, 360),
        )
        reachable = get_reachable_cells(arena)

        self.assertIn((120 // GRID_SIZE, 360 // GRID_SIZE), reachable)
        self.assertNotIn((960 // GRID_SIZE, 360 // GRID_SIZE), reachable)

    def test_point_sized_passage_is_too_narrow_for_player(self):
        gap = 2 * PLAYER_RADIUS - 2
        top_end = (HEIGHT - gap) // 2
        bottom_start = top_end + gap
        arena = ArenaLayout(
            obstacles=[
                pygame.Rect(WIDTH // 2, 0, 20, top_end),
                pygame.Rect(WIDTH // 2, bottom_start, 20, HEIGHT - bottom_start),
            ],
            player1_spawn=(120, 360),
            player2_spawn=(960, 360),
        )

        self.assertNotIn((960 // GRID_SIZE, 360 // GRID_SIZE), get_reachable_cells(arena))

    def test_wide_opening_connects_spawns(self):
        arena = ArenaLayout(
            obstacles=[
                pygame.Rect(WIDTH // 2, 0, 20, 300),
                pygame.Rect(WIDTH // 2, 420, 20, HEIGHT - 420),
            ],
            player1_spawn=(120, 360),
            player2_spawn=(960, 360),
        )

        self.assertIn((960 // GRID_SIZE, 360 // GRID_SIZE), get_reachable_cells(arena))

    def test_blocked_start_has_no_reachable_cells(self):
        arena = create_fixed_arena()
        arena.player1_spawn = arena.obstacles[0].center

        self.assertEqual(get_reachable_cells(arena), set())


class CollisionGeometryTests(unittest.TestCase):
    def test_actual_player_radius_is_unchanged(self):
        self.assertEqual(Player1(0, 0).radius, 18)

    def test_shared_geometry_preserves_edge_and_corner_rules(self):
        obstacle = Obstacle(100, 100, (80, 60), 'white')
        cases = [
            ((82, 120), False),       # Exact edge tangency.
            ((83, 120), True),
            ((88, 88), True),         # Inside the circle's rounded corner.
            ((87, 87), False),
            ((50, 120), False),
            ((120, 120), True),       # Circle center inside the obstacle.
            ((198, 120), False),
            ((82.5, 120), True),      # Preserve float positions in gameplay.
        ]
        for center, expected in cases:
            with self.subTest(center=center):
                player = Player1(*center)
                self.assertEqual(player.collision(obstacle), expected)
                self.assertEqual(
                    circle_intersects_rect(center, player.radius, obstacle.rect), expected,
                )


if __name__ == "__main__":
    unittest.main()
