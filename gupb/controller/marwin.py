import math, random

from gupb.model import arenas
from gupb.model import characters
from typing import NamedTuple, Optional
from gupb.model.coordinates import Coords
from collections import deque

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.DO_NOTHING,
]

WEAPONS_ORDER = {  ## which weapon is better for the current map (isolated_shrine)
    "Knife": 0,
    "Bow": 2,
    "Axe":  5,
    "Amulet": 4,
    "Sword": 3,
}

BLOCKERS = ["=", "#"]

class BaseMarwinController:
    def __init__(self, first_name: str):
        self.first_name = first_name
        self._initial_health = characters.CHAMPION_STARTING_HP
        self._current_facing = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BaseMarwinController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    @property
    def name(self) -> str:
        return f'{self.__class__.__name__}--{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET
    
    def _get_champion(self, knowledge: characters.ChampionKnowledge) -> characters.ChampionDescription:
        position = knowledge.position
        return knowledge.visible_tiles[position].character

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

class WiseTankController(BaseMarwinController):
    def __init__(self, first_name):
        super(WiseTankController, self).__init__(first_name)
        self.arena = self._parse_arena()
        self.precalculated_path = None
        self.next_move = None
        self._menhir_coords = Coords(9, 9)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        if self.precalculated_path is not None:
            self.precalculated_path.clear()
        self.precalculated_path = None

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        ## first of all we want to be as close to the fixed menhir as possible, because this way we can avoid mist in the long run

        my_position = knowledge.position
        my_character = self._get_champion(knowledge)
        action = characters.Action.DO_NOTHING

        ############################## ATTACK

        self._current_facing = my_character.facing  # current facing update logic should be modified and complicated
        
        weapon_cls = EvaderController._get_weapon_for_description(my_character.weapon.name)
        enemies_facing_our_way = self._scan_for_enemies(knowledge)
        if enemies_facing_our_way:
            if self._are_enemies_in_reach(enemies_facing_our_way, weapon_cls,
                                    knowledge.visible_tiles, knowledge.position):
                action = characters.Action.ATTACK

        ############################## ATTACK END

        if self.precalculated_path is None:
            self.precalculated_path = self.find_path(my_position, self._menhir_coords)[1:]  # without position we're standing on
        
        if my_position in self.precalculated_path:
            self.precalculated_path.remove(my_position)

        if my_position == self._menhir_coords:
            return characters.Action.TURN_LEFT

        if not self.next_move:
            self.next_move = self.precalculated_path[0]

        next_facing = self._get_next_facing(my_position, self.next_move)
        if next_facing == my_character.facing:
            if not self._is_position_occupied(self.next_move, knowledge.visible_tiles):
                action = characters.Action.STEP_FORWARD
                # self.precalculated_path.remove(self.next_move)
                self.next_move = None
            else:
                action = characters.Action.ATTACK
        else:
            action = self._get_action_for_facing(my_character.facing, next_facing)

        return action

    def _parse_arena(self):
        with open("./resources/arenas/isolated_shrine.gupb", 'r') as f:
            return [row for row in f.readlines()]
    
    @staticmethod
    def _is_position_occupied(position, tiles):
        return tiles[position].character is not None

    @staticmethod
    def _get_next_facing(current_position, next_position):
        facings = [characters.Facing.LEFT, characters.Facing.RIGHT, characters.Facing.UP, characters.Facing.DOWN]
        for facing in facings:
            if (current_position + facing.value) == next_position:
                return facing
        return characters.Facing.LEFT
    
    @staticmethod
    def _get_action_for_facing(current_facing, next_facing):
        if current_facing.turn_right() == next_facing:
            return characters.Action.TURN_RIGHT
        return characters.Action.TURN_LEFT

    def find_path(self, start, dst):
        width = height = 19
        queue = deque([[start]])
        seen = set([start])  # set literal
        while queue:
            path = queue.popleft()
            tile = path[-1]
            if tile == dst:
                return path
            for x2, y2 in ((tile.x + 1, tile.y), (tile.x - 1, tile.y), (tile.x, tile.y + 1), (tile.x, tile.y - 1)):
                if (0 <= x2 < width) and (0 <= y2 < height) and (self.arena[y2][x2] not in BLOCKERS) and Coords(x2, y2) not in seen:
                    queue.append(path + [Coords(x2, y2)])
                    seen.add(Coords(x2, y2))

    ############################## ATTACK METHODS ##############################
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
    ############################## ATTACK METHODS END ##############################



class EvaderController(BaseMarwinController):

    def __init__(self, first_name: str):
        super().__init__(first_name)

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


## Auxiliary methods
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
    WiseTankController("MarwinWise"),
    EvaderController("Marwin"),
]
