import numpy as np

from gupb.model import coordinates

from .constants import (
    _ITEM_FEATURE_DIM,
    _ITEM_SLOT_DIM,
    _ITEM_WEAPON_DIM,
    _MAX_NEAREST_ITEMS,
    _normalize_distance,
    item_slot_offset,
)
from .weapons_encoding import encode_direction, item_weapon_one_hot

ItemEntry = tuple[int, int, int, str]


def _default_item_slot(out: np.ndarray, slot: int) -> None:
    base = item_slot_offset(slot)
    out[base : base + _ITEM_WEAPON_DIM] = item_weapon_one_hot("knife")
    out[base + _ITEM_WEAPON_DIM] = 1.0
    out[base + _ITEM_WEAPON_DIM + 1] = 0.0
    out[base + _ITEM_WEAPON_DIM + 2] = 0.0


def _encode_nearest_items(
    items: list[ItemEntry],
    start: coordinates.Coords,
) -> np.ndarray:
    out = np.empty(_ITEM_FEATURE_DIM, dtype=np.float32)
    for i in range(_MAX_NEAREST_ITEMS):
        _default_item_slot(out, i)
    for i, (distance, x, y, weapon_type) in enumerate(items[:_MAX_NEAREST_ITEMS]):
        base = item_slot_offset(i)
        out[base : base + _ITEM_WEAPON_DIM] = item_weapon_one_hot(weapon_type)
        out[base + _ITEM_WEAPON_DIM] = _normalize_distance(distance)
        cos_t, sin_t = encode_direction(start, coordinates.Coords(x, y))
        out[base + _ITEM_WEAPON_DIM + 1] = cos_t
        out[base + _ITEM_WEAPON_DIM + 2] = sin_t
    return out
