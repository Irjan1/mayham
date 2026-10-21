"""Persistent upgrade data and calculations, without Pygame or rendering."""

from random import Random

from config import (
    BULLET_COOLDOWN, BULLET_DAMAGE, BULLET_RADIUS, EXPLOSION_RADII, STARTING_HEALTH, THRUST,
)


MAX_UPGRADE_LEVEL = 2
HULL_HEALTH_PER_LEVEL = 0.20
RAPID_FIRE_REDUCTION_PER_LEVEL = 0.15
THRUST_INCREASE_PER_LEVEL = 0.15
BULLET_RADIUS_PER_LEVEL = 0.25
BULLET_DAMAGE_PER_LEVEL = 0.20

UPGRADES = {
    "reinforced_hull": {
        "name": "Reinforced Hull",
        "effects": tuple(f"+{HULL_HEALTH_PER_LEVEL * level:.0%} maximum health"
                         for level in range(1, MAX_UPGRADE_LEVEL + 1)),
        "max_level": MAX_UPGRADE_LEVEL,
    },
    "rapid_fire": {
        "name": "Rapid Fire",
        "effects": tuple(f"{RAPID_FIRE_REDUCTION_PER_LEVEL * level:.0%} shorter shooting cooldown"
                         for level in range(1, MAX_UPGRADE_LEVEL + 1)),
        "max_level": MAX_UPGRADE_LEVEL,
    },
    "enhanced_thrusters": {
        "name": "Enhanced Thrusters",
        "effects": tuple(f"+{THRUST_INCREASE_PER_LEVEL * level:.0%} thrust acceleration"
                         for level in range(1, MAX_UPGRADE_LEVEL + 1)),
        "max_level": MAX_UPGRADE_LEVEL,
    },
    "larger_bullets": {
        "name": "Larger Bullets",
        "effects": tuple(f"+{BULLET_RADIUS_PER_LEVEL * level:.0%} bullet radius"
                         for level in range(1, MAX_UPGRADE_LEVEL + 1)),
        "max_level": MAX_UPGRADE_LEVEL,
    },
    "heavy_bullets": {
        "name": "Heavy Bullets",
        "effects": tuple(f"+{BULLET_DAMAGE_PER_LEVEL * level:.0%} bullet damage"
                         for level in range(1, MAX_UPGRADE_LEVEL + 1)),
        "max_level": MAX_UPGRADE_LEVEL,
    },
    "ricochet": {
        "name": "Ricochet",
        "effects": ("1 surface bounce", "2 surface bounces"),
        "max_level": MAX_UPGRADE_LEVEL,
    },
    "explosive_rounds": {
        "name": "Explosive Rounds",
        "effects": tuple(f"{radius} px blast radius" for radius in EXPLOSION_RADII[1:]),
        "max_level": MAX_UPGRADE_LEVEL,
    },
}


def create_upgrade_levels() -> dict[str, int]:
    """Give each player a separate set of levels for a new game session."""
    return {upgrade_id: 0 for upgrade_id in UPGRADES}


def choose_upgrade_offers(levels: dict[str, int], rng: Random, count: int = 3) -> list[str]:
    """Sample eligible upgrades without duplicates, including from future larger pools."""
    eligible = [upgrade_id for upgrade_id, upgrade in UPGRADES.items()
                if levels.get(upgrade_id, 0) < upgrade["max_level"]]
    return rng.sample(eligible, min(count, len(eligible)))


def apply_upgrade(levels: dict[str, int], upgrade_id: str) -> bool:
    """Increase one level if it exists and has not reached its cap."""
    if upgrade_id not in UPGRADES:
        return False
    current_level = levels.get(upgrade_id, 0)
    if current_level >= UPGRADES[upgrade_id]["max_level"]:
        return False
    levels[upgrade_id] = current_level + 1
    return True


def effective_stats(levels: dict[str, int]) -> dict[str, int | float]:
    """Derive totals from original values, never from an already upgraded player."""
    hull_level = levels.get("reinforced_hull", 0)
    rapid_fire_level = levels.get("rapid_fire", 0)
    thruster_level = levels.get("enhanced_thrusters", 0)
    size_level = levels.get("larger_bullets", 0)
    damage_level = levels.get("heavy_bullets", 0)
    return {
        "max_health": round(STARTING_HEALTH * (1 + HULL_HEALTH_PER_LEVEL * hull_level)),
        "bullet_cooldown": round(BULLET_COOLDOWN * (1 - RAPID_FIRE_REDUCTION_PER_LEVEL * rapid_fire_level)),
        "thrust": THRUST * (1 + THRUST_INCREASE_PER_LEVEL * thruster_level),
        "bullet_radius": round(BULLET_RADIUS * (1 + BULLET_RADIUS_PER_LEVEL * size_level)),
        "bullet_damage": round(BULLET_DAMAGE * (1 + BULLET_DAMAGE_PER_LEVEL * damage_level)),
        "bullet_bounces": levels.get("ricochet", 0),
        "explosion_radius": EXPLOSION_RADII[levels.get("explosive_rounds", 0)],
    }
