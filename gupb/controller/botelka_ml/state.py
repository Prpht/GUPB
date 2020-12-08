from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

import numpy as np

from gupb.model.arenas import Arena
from gupb.model.characters import ChampionKnowledge, Facing
from gupb.model.coordinates import Coords, sub_coords
from gupb.model.weapons import Weapon, Axe, Sword, Amulet, Knife, Bow, WeaponDescription

WEAPONS = {
    "bow": Bow(),
    "axe": Axe(),
    "sword": Sword(),
    "knife": Knife(),
    "amulet": Amulet(),
}

WEAPON_TO_INT = {
    "bow": 0,
    "axe": 1,
    "sword": 2,
    "knife": 3,
    "amulet": 4,
}

FACING_TO_INT = {
    Facing.UP: 0,
    Facing.RIGHT: 1,
    Facing.LEFT: 2,
    Facing.DOWN: 3
}

MAX_HEALTH = 5


def weapon_ranking_by_desc(weapon: WeaponDescription) -> int:
    if weapon.name == 'amulet':
        return 10
    if weapon.name == 'bow':
        return 8
    if weapon.name == 'axe':
        return 6
    if weapon.name == 'sword':
        return 6
    return 0


class DistanceMeasure(Enum):
    CLOSE = 0
    FAR = 1
    VERY_FAR = 2
    INACCESSIBLE = 3


@dataclass
class State:
    arena: Arena
    bot_coords: Coords
    health: int
    visible_enemies: List[Coords]
    can_attack_enemy: bool
    facing: Facing
    weapon: Weapon
    distance_to_menhir: int
    menhir_coords: Coords
    tick: int
    weapons_info: Dict[Coords, WeaponDescription]
    mist_visible: bool

    @staticmethod
    def get_length():
        return 11

    def as_tuple(self):
        return (
            hash(self.arena.name), self.bot_coords.x, self.bot_coords.y, self.health, len(self.visible_enemies),
            self.can_attack_enemy, FACING_TO_INT[self.facing], self.distance_to_menhir, self.menhir_coords.x,
            self.menhir_coords.y, self.tick
        )


def get_state(knowledge: ChampionKnowledge, arena: Arena, tick: int,
              weapons_prior_info: Dict[Coords, WeaponDescription]) -> State:
    bot_coords = knowledge.position
    bot_tile = knowledge.visible_tiles.get(bot_coords)
    bot_character = bot_tile.character if bot_tile else None
    bot_weapon = bot_character.weapon.name if bot_character else "knife"
    bot_facing = bot_character.facing if bot_character else Facing.UP

    # ---

    health = bot_character.health if bot_character else 5

    visible_enemies = [
        Coords(*coords)
        for coords, tile in knowledge.visible_tiles.items()
        if tile.character and coords != bot_coords
    ]

    can_attack_enemy = any(
        coord
        for coord in
        WEAPONS[bot_weapon].cut_positions(arena.terrain, bot_coords, bot_facing)
        if coord in knowledge.visible_tiles and knowledge.visible_tiles[coord].character
    )

    menhir_det = sub_coords(bot_coords, arena.menhir_position)
    menhir_distance = np.sqrt(menhir_det.x ** 2 + menhir_det.y ** 2)

    visible_weapons = {
        Coords(*coords): tile.loot
        for coords, tile in knowledge.visible_tiles.items()
        if tile.loot and coords != bot_coords
    }

    old_weapons = {
        coords: weapon
        for (coords, weapon) in weapons_prior_info.items()
        if coords not in visible_weapons.keys() or visible_weapons.get(coords) == weapon
    }

    weapons = {**old_weapons, **visible_weapons}
    if bot_coords in weapons:
        del weapons[bot_coords]

    mist_visible = any(
        visible_tile
        for visible_tile in knowledge.visible_tiles.values()
        if "mist" in {effect.type for effect in visible_tile.effects}
    )

    return State(
        arena,
        bot_coords,
        health,
        visible_enemies,
        can_attack_enemy,
        bot_facing,
        WEAPONS[bot_weapon],
        menhir_distance,
        arena.menhir_position,
        tick,
        weapons,
        mist_visible
    )
