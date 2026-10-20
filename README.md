# Mayham

A local two-player rocket combat game built with Python and Pygame.

Players battle in a small arena using physics-based movement, projectiles, and limited fuel. The game is designed around fast rounds where aggressive movement and fuel management are essential.

![Mayham gameplay](docs/images/gameplay.png)

## Gameplay

- Two-player local multiplayer
- A new procedural arena each round
- Open, corridor and scattered room styles with L-shaped and U-shaped cover
- Red spike zones and tan destructible blocks in some rooms
- Rocket movement with gravity and thrust
- Circular player hitboxes and obstacle collision detection
- Projectiles, health, and damage
- Limited fuel with randomly spawning fuel pickups
- Round-based gameplay with persistent scores

## Controls

| Action | Player 1 | Player 2 |
|---|---|---|
| Rotate left | Left Arrow | A |
| Rotate right | Right Arrow | D |
| Thrust | Up Arrow | W |
| Shoot | Right Shift | Space |

## Installation

Requires Python 3.13 and Pygame.

Create and activate a virtual environment:

`python3.13 -m venv .venv`

`source .venv/bin/activate`

Install Pygame:

`python -m pip install pygame`

Run the game:

`python main.py`

## Arena seeds and previews

The terminal prints the arena seed at the start of each round. Reproduce a room
with `python main.py --seed 42`. Later rounds use 43, 44, and so on. Fuel uses a
separate random generator, so pickups do not change the arena sequence.

Use `python main.py --fixed-arena` to play the original room for debugging.

Room styles are chosen from the seed by default. To play one style across rounds,
use `python main.py --seed 42 --style corridors` (`open` and `scattered` also work).
The terminal prints both the seed and style. The same seed and style reproduce a
layout with the current generator version; changing generation rules may change it.

White obstacles are permanent. Tan blocks break after three bullets, with cracks
showing damage. Each rectangular part of a grouped shape can be destroyed separately.
Red spike zones kill on contact and award the opponent the round, like a lethal crash.
Safe routes and fuel placement avoid these zones. Breaking blocks opens new fuel
locations without changing the original seeded layout or fuel quantities and timing.

Preview arenas without opening a game window:

```sh
python -m tools.preview_arenas --seed 42 --output arena42.png
python -m tools.preview_arenas --start 0 --count 12 --output arena_grid.png
python -m tools.preview_arenas --start 0 --count 6 --style corridors --output corridors.png
```

Previews show room style, obstacle rectangles, spikes, breakable blocks, player
spawn circles and each arena's seed. A color legend appears below the grid.
Fuel positions use the ship-reachable grid region, check the full pickup rectangle,
and leave space around current player positions.

## Implementation

The game uses object-oriented Python, with shared player behavior, separate gameplay entities, and Pygame sprite groups.

Collision detection uses circular player hitboxes against rectangular obstacles. Physics, projectile handling, fuel management, and round logic are implemented in separate components.

## Tests

With Pygame installed, run the tests from the project root:

`python -m unittest discover -s tests -v`

Game setup tests use SDLs dummy drivers, so they do not open a game window.

## Authors

Developed by Irjan Evertsen and Emil Olsen-Kristiansen as a university project for INF-1400 at UiT – The Arctic University of Norway.
