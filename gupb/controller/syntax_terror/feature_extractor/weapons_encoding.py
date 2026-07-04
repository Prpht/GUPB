import math

import numpy as np

from gupb.model import coordinates, tiles

_ITEM_WEAPON_TYPES: tuple[str, ...] = (
    "knife",
    "sword",
    "axe",
    "bow",
    "amulet",
    "scroll",
    "potion",
)
_PLAYER_WEAPON_TYPES: tuple[str, ...] = (
    "knife",
    "sword",
    "axe",
    "bow",
    "amulet",
    "scroll",
)


def item_weapon_one_hot(weapon_type: str) -> np.ndarray:
    out = np.zeros(len(_ITEM_WEAPON_TYPES), dtype=np.float32)
    idx = _ITEM_WEAPON_TYPES.index(weapon_type)
    out[idx] = 1.0
    return out


def player_weapon_one_hot(weapon_name: str) -> np.ndarray:
    base = weapon_name.split("_")[0]
    if base == "bow":
        base = "bow"
    out = np.zeros(len(_PLAYER_WEAPON_TYPES), dtype=np.float32)
    idx = _PLAYER_WEAPON_TYPES.index(base)
    out[idx] = 1.0
    return out


def tile_item_weapon_type(tile: tiles.TileDescription) -> str:
    if tile.consumable:
        return "potion"
    if tile.loot:
        name = tile.loot.name.split("_")[0]
        if name == "bow":
            return "bow"
        return name
    return "knife"


def self_charges_norm(weapon: str, scroll_charges: int) -> float:
    if weapon.split("_")[0] == "scroll":
        return scroll_charges / 5.0
    return 1.0


def encode_direction(
    start: coordinates.Coords,
    target: coordinates.Coords,
) -> tuple[float, float]:
    dx = target[0] - start[0]
    dy = target[1] - start[1]
    mag = math.hypot(dx, dy)
    if mag < 1e-6:
        return 0.0, 0.0
    return dx / mag, dy / mag
