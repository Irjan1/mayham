# Mayham

**A physics-based rocket combat game built with Python and Pygame.**

Mayham is a local two-player arena game where players battle using rockets with deliberately awkward, momentum-based movement.

Manage your limited fuel, fight over pickups, and avoid dangerous collisions while trying to destroy your opponent. Each round takes place in a new procedurally generated arena, and the losing player receives upgrades that make subsequent rounds increasingly chaotic.

The goal is simple: **short, tactical rounds that gradually turn into unpredictable space combat.**

![Mayham gameplay](docs/images/gameplay.png)

## Features

- **Local multiplayer** — Two players compete on the same keyboard.
- **Physics-based movement** — Gravity, thrust, momentum, and bouncing make controlling your rocket part of the challenge.
- **Limited fuel** — Conserve fuel and compete for pickups, which are announced before spawning.
- **Procedural arenas** — Seeded room generation with multiple layouts, obstacles, destructible cover, and lethal hazards.
- **Weapon upgrades** — Improve your rockets with faster firing, heavier bullets, ricochets, explosive rounds, and more.
- **Procedural space backgrounds** — Randomized stars, planets, galaxies, nebulae, and other cosmic scenery.
- **Sci-fi presentation** — Industrial environments, particle effects, and procedurally generated sound effects.

## How to Play

Each player controls a rocket using rotation, thrust, and shooting.

Flying continuously consumes valuable fuel, while losing control can result in damaging collisions. Fuel pickups are announced several seconds before appearing, giving players an opportunity to fight for their location.

After each round, the losing player can choose an upgrade that persists throughout the match.

As upgrades accumulate, the battles become increasingly unpredictable.

### Controls

| Action | Player 1 | Player 2 |
|---|---|---|
| Rotate left | Left Arrow | A |
| Rotate right | Right Arrow | D |
| Thrust | Up Arrow | W |
| Shoot | Right Shift | Space |
| Select upgrade | 1, 2, or 3 | 1, 2, or 3 |

The game includes a main menu and an in-game controls screen.

## Installation

**Requirements:** Python 3.13 and Pygame.

Clone the repository:

```bash
git clone https://github.com/Irjan1/mayham.git
cd mayham
```

Create a virtual environment (recommended):

```bash
python -m venv .venv
```

Activate it:

**Windows:**
```powershell
.venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
source .venv/bin/activate
```

Install Pygame and start the game:

```bash
python -m pip install pygame
python main.py
```

Use the arrow keys and Enter to navigate the main menu.

## Procedural Generation

Mayham generates a new arena each round using a deterministic seed.

Arenas feature different layouts, including open spaces, corridors, and scattered cover. Generation checks that the rooms remain navigable and that players spawn in valid locations.

You can reproduce an arena with a specific seed:

```bash
python main.py --seed 42
```

Or select a particular arena style:

```bash
python main.py --seed 42 --style corridors
```

To play the original fixed arena:

```bash
python main.py --fixed-arena
```

The game also includes tools for previewing generated arenas and space backgrounds without starting a match.

## Development

Mayham began as a university project for **INF-1400 at UiT – The Arctic University of Norway**, developed by Irjan Evertsen and Emil Olsen-Kristiansen.


After the course, the project was continued as a personal project, adding procedural environments, new gameplay mechanics, visual effects, audio, and automated tests. 

The project is primarily developed for fun, while exploring game physics, procedural generation, algorithms, and software design.

### Testing

The project includes automated tests covering procedural generation, collisions, upgrades, gameplay mechanics, and other systems.

Run the tests with:

```bash
python -m unittest discover -s tests -v
```

### Future Plans

Planned additions include:

- An AI-controlled opponent
- More varied upgrades and weapon specializations
- A short single-player campaign
- Additional arena mechanics and environments
- A downloadable Windows release

## Authors

**Irjan Evertsen** and **Emil Olsen-Kristiansen** — Original game.

**Irjan Evertsen** — Continued development and extensions.