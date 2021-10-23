import math, random

from gupb.model import arenas
from gupb.model import characters
from typing import NamedTuple, Optional

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.DO_NOTHING,
]


class EvaderController:

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self._initial_health = characters.CHAMPION_STARTING_HP
        self._current_facing = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EvaderController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        champion = self._get_champion(knowledge)
        if self._current_facing is None:
            self._current_facing = champion.facing
        self._current_facing = champion.facing  # current facing update logic should be modified and complicated
        
        weapon_cls = EvaderController._get_weapon_for_description(champion.weapon.name)
        enemies_facing_our_way = self._scan_for_enemies(knowledge)
        if enemies_facing_our_way:
            if self._are_enemies_in_reach(enemies_facing_our_way, weapon_cls,
                                    knowledge.visible_tiles, knowledge.position):
                action = characters.Action.ATTACK
            else:
                action = characters.Action.TURN_LEFT

        else:
            action = random.choice(POSSIBLE_ACTIONS)
        return action  # DO_NOTHING

    def _get_champion(self, knowledge: characters.ChampionKnowledge) -> characters.ChampionDescription:
        position = knowledge.position
        return knowledge.visible_tiles[position].character
    
    def _are_enemies_in_reach(self, enemies, weapon_cls, sight_area, position):
        weapon_reach = self._get_cut_positions(weapon_cls, sight_area, position)
        for enemy in enemies:
            if enemy in weapon_reach:
                return True
    
    def _get_cut_positions(self, weapon_cls, sight_area, position):
        try:
            weapon_reach = weapon_cls.cut_positions(sight_area, position, self._current_facing)
        except AttributeError:
            weapon_reach = _get_cut_positions(weapon_cls, sight_area, position, self._current_facing)
        return weapon_reach

    def _scan_for_enemies(self, knowledge: characters.ChampionKnowledge) -> Optional[NamedTuple]:
        tiles_in_sight = knowledge.visible_tiles
        my_character = self._get_champion(knowledge)
        enemies_facing_our_way = []
        for tile, tile_desc in tiles_in_sight.items():
            if tile_desc.character and tile_desc.character != my_character:  ## enemy in sight
                enemies_facing_our_way.append(tile)

        return enemies_facing_our_way or None

    def _calc_distance(self, enemies) -> float:
        nearest = math.inf
        for position in enemies:
            distance = (position[0] ** 2 + position[1] ** 2) ** 0.5
            if distance < nearest:
                nearest = distance
        return nearest

    @property
    def name(self) -> str:
        return f'EvaderController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET
    
    @staticmethod
    def _get_weapon_for_description(weapon_description: str):
        from gupb.model import weapons

        weapons_cls = {
            'knife': weapons.Knife,
            'sword': weapons.Sword,
            'bow': weapons.Bow,
            'axe': weapons.Axe,
            'amulet': weapons.Amulet
        }
        for key, weapon in weapons_cls.items():
            if key in weapon_description.lower():
                return weapon
        return None


def _is_tile_transparent(tile_name):
    from gupb.model import tiles
    tiles_cls = {
        'wall': tiles.Wall,
        'sea': tiles.Sea,
        'land': tiles.Land,
        'menhir': tiles.Menhir
    }

    for key, tile_cls in tiles_cls.items():
        if key in tile_name.lower():
            return tile_cls.terrain_transparent()
    return True


def _get_cut_positions(weapon_cls, terrain, position, facing):
    cut_positions = []
    cut_position = position
    for _ in range(weapon_cls.reach()):
        cut_position += facing.value
        if cut_position not in terrain:
            break
        cut_positions.append(cut_position)
        if not _is_tile_transparent(terrain[cut_position].type):
            break
    return cut_positions


POTENTIAL_CONTROLLERS = [
    EvaderController("Marwin"),
]
