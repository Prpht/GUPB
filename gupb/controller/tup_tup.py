from typing import Dict, Type, Optional

from gupb.model import arenas, coordinates, weapons, tiles
from gupb.model import characters


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class TupTupController:
    def __init__(self, name_suffix):
        self.identifier: str = "TupTup" + name_suffix
        self.menhir_pos: coordinates.Coords = None
        self.facing: Optional[characters.Facing] = None
        self.weapon: Type[weapons.Weapon] = weapons.Knife

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TupTupController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.identifier)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_pos = arena_description.menhir_position

    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.__update_char_info(knowledge.visible_tiles[knowledge.position].character)

        if self.__is_enemy_in_range(knowledge.position, knowledge.visible_tiles):
            return characters.Action.ATTACK

        return characters.Action.DO_NOTHING

    def __update_char_info(self, char_description: characters.ChampionDescription) -> None:
        self.weapon = char_description.weapon
        self.facing = char_description.facing

    def __is_enemy_in_range(self, position: coordinates.Coords,
                            visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
        try:
            if isinstance(self.weapon, weapons.LineWeapon):
                weapon_reach = self.weapon.reach()
                tile_to_check = position
                for _ in range(1, self.weapon.reach() + 1):
                    tile_to_check = tile_to_check + self.facing
                    if visible_tiles[tile_to_check].character:
                        return True
            elif isinstance(self.weapon, weapons.Amulet):   # only sees the tile in front
                if visible_tiles[position + self.facing].character:
                    return True
            elif isinstance(self.weapon, weapons.Axe):
                tiles_to_check = [coordinates.Coords(self.facing.value.x, i) for i in [-1, 0, 1]] \
                    if self.facing.value.x != 0 else [coordinates.Coords(i, self.facing.value.y) for i in [-1, 0, 1]]
                for tile in tiles_to_check:
                    if tile in visible_tiles and visible_tiles[position + self.facing].character:
                        return True
        except KeyError:
            # tile was not visible
            pass
        finally:
            return False

    @property
    def name(self) -> str:
        return self.identifier


POTENTIAL_CONTROLLERS = [
    TupTupController('1'),
]
