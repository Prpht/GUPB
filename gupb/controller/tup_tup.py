from enum import Enum
from queue import SimpleQueue
from typing import Dict, Type, Optional

from gupb.model import arenas, coordinates, weapons, tiles
from gupb.model import characters

FACING_ORDER = [characters.Facing.LEFT, characters.Facing.UP, characters.Facing.RIGHT, characters.Facing.DOWN]


# class MoveOptions(Enum):
#     MOVE_VERTICALLY,
#     MOVE_HORIZONTALLY

# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class TupTupController:
    def __init__(self, name_suffix):
        self.identifier: str = "TupTup" + name_suffix
        self.menhir_pos: coordinates.Coords = None
        self.facing: Optional[characters.Facing] = None
        self.position: coordinates.Coords = None
        self.weapon: Type[weapons.Weapon] = weapons.Knife
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TupTupController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.identifier)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_pos = arena_description.menhir_position

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.__update_char_info(knowledge)

        if self.__is_enemy_in_range(knowledge.position, knowledge.visible_tiles):
            return characters.Action.ATTACK

        self.display_info(knowledge)

        if not self.action_queue.empty():
            return self.action_queue.get()
        self.move(knowledge)

        return characters.Action.DO_NOTHING

    def move(self, knowledge):
        x_distance, y_distance = self.calc_coords_diff(self.menhir_pos, self.position)

        expected_facing = self.facing
        if x_distance or y_distance:  # if there is a need to move
            if y_distance == 0 or abs(x_distance) <= abs(y_distance):  # changes in horizontal direction
                expected_facing = self.get_expected_facing(x_distance, 'horizontal')
            else:  # changes in vertical direction
                expected_facing = self.get_expected_facing(y_distance, 'vertical')

        if self.facing != expected_facing:
            self.rotate(expected_facing)
        elif self.can_move_forward(self.position, self.facing, knowledge):
            self.action_queue.put(characters.Action.STEP_FORWARD)
        else:
            self.avoid_obstacle()  # todo for now ATTACK to see the result
        self.display_info(knowledge)

    def rotate(self, expected_facing):
        curr_facing_index = FACING_ORDER.index(self.facing)
        expected_facing_index = FACING_ORDER.index(expected_facing)

        diff_expected_curr = expected_facing_index - curr_facing_index
        if diff_expected_curr < 0:
            diff_expected_curr += len(FACING_ORDER)

        if diff_expected_curr == 1:
            self.action_queue.put(characters.Action.TURN_RIGHT)
        elif diff_expected_curr == 2:
            self.action_queue.put(characters.Action.TURN_RIGHT)
            self.action_queue.put(characters.Action.TURN_RIGHT)
        elif diff_expected_curr == 3:
            self.action_queue.put(characters.Action.TURN_LEFT)

    def get_expected_facing(self, distance, direction):
        if direction == 'vertical':
            if distance < 0:
                return characters.Facing.UP
            elif distance > 0:
                return characters.Facing.DOWN
        elif direction == 'horizontal':
            if distance < 0:
                return characters.Facing.LEFT
            elif distance > 0:
                return characters.Facing.RIGHT

    def can_move_forward(self, position, facing, knowledge):
        next_tile_coords = position + facing.value
        return next_tile_coords in knowledge.visible_tiles.keys() \
               and knowledge.visible_tiles[next_tile_coords].type == 'land'

    def avoid_obstacle(self):
        # check if the same (x,y) [as when started]
        # check if the same 'facing'
        self.action_queue.put(characters.Action.ATTACK)

    def display_info(self, knowledge: characters.ChampionKnowledge):
        character = knowledge.visible_tiles[knowledge.position].character
        hero_info = {'weapon': character.weapon, 'facing': character.facing, 'position': knowledge.position}
        print("Menhir position ", self.menhir_pos)
        print("Hero ", hero_info['weapon'], hero_info['facing'], hero_info['position'])

    def calc_coords_diff(self, end_coords, start_coords):
        coords_dif = coordinates.sub_coords(end_coords, start_coords)
        return coords_dif

    def __update_char_info(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position
        char_description = knowledge.visible_tiles[knowledge.position].character
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
            elif isinstance(self.weapon, weapons.Amulet):  # only sees the tile in front
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
