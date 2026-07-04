from __future__ import annotations

from collections.abc import Callable

from gupb.model import characters
from gupb.model import coordinates

from .utils import TRANSPARENT_TILE_TYPES, to_coords

WEAPON_BASE_BY_NAME = {
    "knife": "knife",
    "sword": "sword",
    "axe": "axe",
    "amulet": "amulet",
    "scroll": "scroll",
    "bow": "bow",
    "bow_loaded": "bow",
    "bow_unloaded": "bow",
}

WEAPON_RANK = {
    "amulet": 1,
    "knife": 2,
    "scroll": 3,
    "axe": 4,
    "sword": 5,
    "bow_unloaded": 6,
    "bow_loaded": 7,
    "bow": 7,
}

WEAPON_DAMAGE = {
    "knife": 2,
    "sword": 2,
    "axe": 3,
    "amulet": 2,
    "scroll": 3,
    "bow_unloaded": 0,
    "bow_loaded": 3,
    "bow": 3,
}

LINE_WEAPON_REACH = {
    "knife": 1,
    "sword": 3,
    "scroll": 1,
    "bow_loaded": 50,
    "bow_unloaded": 50,
    "bow": 50,
}


def weapon_base(weapon_name: str | None) -> str:
    if not weapon_name:
        return "knife"
    known = WEAPON_BASE_BY_NAME.get(weapon_name)
    if known is not None:
        return known
    separator = weapon_name.find("_")
    return weapon_name if separator < 0 else weapon_name[:separator]


def weapon_rank(weapon_name: str | None) -> int:
    if not weapon_name:
        return WEAPON_RANK["knife"]
    return WEAPON_RANK.get(weapon_name, WEAPON_RANK.get(weapon_base(weapon_name), 1))


def weapon_damage(weapon_name: str | None) -> int:
    if not weapon_name:
        return WEAPON_DAMAGE["knife"]
    return WEAPON_DAMAGE.get(weapon_name, WEAPON_DAMAGE.get(weapon_base(weapon_name), 2))


def weapon_ready_to_damage(weapon_name: str | None) -> bool:
    return weapon_damage(weapon_name) > 0


def is_weapon_upgrade(current_weapon: str | None, loot_weapon: str | None) -> bool:
    if not loot_weapon:
        return False
    current_rank = weapon_rank(current_weapon)
    loot_rank = weapon_rank(loot_weapon)
    if weapon_base(current_weapon or "knife") == weapon_base(loot_weapon):
        return False
    return loot_rank > current_rank


def cut_positions(
    weapon_name: str | None,
    position: coordinates.Coords | tuple[int, int],
    facing: characters.Facing,
    tile_type_at: Callable[[coordinates.Coords], str | None],
    character_at: Callable[[coordinates.Coords], object | None] | None = None,
    ignore_characters: bool = False,
) -> tuple[coordinates.Coords, ...]:
    position = to_coords(position)
    weapon_name = weapon_name or "knife"

    if weapon_name == "axe":
        centre = position + facing.value
        return (
            centre + facing.turn_left().value,
            centre,
            centre + facing.turn_right().value,
        )

    if weapon_name == "amulet":
        return (
            coordinates.Coords(position.x + 1, position.y + 1),
            coordinates.Coords(position.x - 1, position.y + 1),
            coordinates.Coords(position.x + 1, position.y - 1),
            coordinates.Coords(position.x - 1, position.y - 1),
            coordinates.Coords(position.x + 2, position.y + 2),
            coordinates.Coords(position.x - 2, position.y + 2),
            coordinates.Coords(position.x + 2, position.y - 2),
            coordinates.Coords(position.x - 2, position.y - 2),
        )

    reach = LINE_WEAPON_REACH.get(weapon_name, LINE_WEAPON_REACH.get(weapon_base(weapon_name)))
    if reach is None:
        return tuple()

    result: list[coordinates.Coords] = []
    current = position
    for _ in range(reach):
        current = current + facing.value
        tile_type = tile_type_at(current)
        if tile_type is None:
            break
        result.append(current)
        if tile_type not in TRANSPARENT_TILE_TYPES:
            break
        if not ignore_characters and character_at is not None and character_at(current) is not None:
            break
    return tuple(result)


def can_hit(
    weapon_name: str | None,
    attacker_position: coordinates.Coords,
    attacker_facing: characters.Facing,
    target_position: coordinates.Coords,
    tile_type_at: Callable[[coordinates.Coords], str | None],
    character_at: Callable[[coordinates.Coords], object | None] | None = None,
) -> bool:
    if not weapon_ready_to_damage(weapon_name):
        return False
    return target_position in cut_positions(
        weapon_name,
        attacker_position,
        attacker_facing,
        tile_type_at,
        character_at,
        ignore_characters=False,
    )
