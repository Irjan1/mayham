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
- Between-round upgrades for the losing player, lasting for the game session

## Controls

| Action | Player 1 | Player 2 |
|---|---|---|
| Rotate left | Left Arrow | A |
| Rotate right | Right Arrow | D |
| Thrust | Up Arrow | W |
| Shoot | Right Shift | Space |
| Choose upgrade when offered | 1, 2, or 3 | 1, 2, or 3 |

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

A starting seed, such as `python main.py --seed 42`, reproduces the match's arena
sequence. Arena seeds still increment each round: 42, 43, 44, and so on. The terminal
prints both the arena seed and its style. To reproduce one particular room, use
both values, for example `python main.py --seed 44 --style scattered`.

Styles rotate through a shuffled bag containing one `open`, one `corridors`, and
one `scattered` room. Each bag uses every style, and its first style differs from
the previous bag's last style. Separate random generators handle style rotation,
upgrade offers and fuel, so choosing an upgrade cannot change later arenas.

Use `python main.py --fixed-arena` to play the original room for debugging.

To bypass style rotation and play one style across rounds,
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

## Between-round upgrades

After the winner announcement, the losing player chooses an upgrade with 1, 2, or 3.
Movement, bullets and fuel stop while the screen is open. The selected card briefly
highlights, then the next round starts. Draws skip selection. Maxed upgrades are not
offered; fewer remaining upgrades mean fewer cards, and no eligible cards means the
next round starts immediately after the announcement.

| Upgrade | Level 1 total | Level 2 total |
|---|---|---|
| Reinforced Hull | +20% maximum health | +40% maximum health |
| Rapid Fire | 15% shorter shooting cooldown | 30% shorter shooting cooldown |
| Enhanced Thrusters | +15% thrust acceleration | +30% thrust acceleration |

Each upgrade stops at level 2. Each player keeps their own levels for the whole game
session, even after winning later rounds. New rounds start at the upgraded maximum
health. Gravity, rotation, fuel consumption and bullet damage stay unchanged.

Stats are calculated from the original values each round, so bonuses do not compound.
Restarting the application or constructing a new `Game` resets upgrade levels.
Upgrade definitions, eligibility and stat calculations live in `src/upgrades.py`;
the selection screen only renders cards. No upgrade rarity or pickup system is added.

## Implementation

The game uses object-oriented Python, with shared player behavior, separate gameplay entities, and Pygame sprite groups.

Collision detection uses circular player hitboxes against rectangular obstacles. Physics, projectile handling, fuel management, and round logic are implemented in separate components.

## Tests

With Pygame installed, run the tests from the project root:

`python -m unittest discover -s tests -v`

Game setup tests use SDLs dummy drivers, so they do not open a game window.

## Authors

Developed by Irjan Evertsen and Emil Olsen-Kristiansen as a university project for INF-1400 at UiT – The Arctic University of Norway.
