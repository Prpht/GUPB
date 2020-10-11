from queue import SimpleQueue
from typing import Dict, Type, Optional

from gupb.model import arenas, coordinates, weapons, tiles
from gupb.model import characters

FACING_ORDER = [characters.Facing.LEFT, characters.Facing.UP, characters.Facing.RIGHT, characters.Facing.DOWN]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class TupTupController:
    def __init__(self, name_suffix):
        self.identifier: str = "TupTup" + name_suffix
        self.menhir_pos: coordinates.Coords = None
        self.facing: Optional[characters.Facing] = None
        self.position: coordinates.Coords = None
        self.weapon: Type[weapons.Weapon] = weapons.Knife
        self.reached_middle: bool = False
        self.direction: Optional[characters.Facing] = None
        self.moved: bool = False
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TupTupController) and other.name == self.name:
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

        if not self.action_queue.empty():
            return self.action_queue.get()

        if self.direction:
            self.__avoid_obstacle(knowledge)
        elif not self.reached_middle:
            self.__move(knowledge)
        else:
            self.__guard_area()

        return self.action_queue.get()

    def __update_char_info(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position
        char_description = knowledge.visible_tiles[knowledge.position].character
        self.weapon = char_description.weapon
        self.facing = char_description.facing

    def __move(self, knowledge: characters.ChampionKnowledge) -> None:
        x_distance, y_distance = self.__calc_coords_diff(self.menhir_pos, self.position)
        if abs(x_distance) < 2 and abs(y_distance) < 2:
            self.reached_middle = True
            self.action_queue.put(characters.Action.TURN_RIGHT)
            return None

        if x_distance == 0:     # changes in vertical direction
            expected_facing = self.__get_expected_facing(y_distance, True)
        elif y_distance == 0 or abs(x_distance) <= abs(y_distance):  # changes in horizontal direction
            expected_facing = self.__get_expected_facing(x_distance, False)
        else:                   # changes in vertical direction
            expected_facing = self.__get_expected_facing(y_distance, True)

        if self.facing != expected_facing:
            self.__rotate(expected_facing)
        elif self.__can_move_forward(knowledge):
            self.action_queue.put(characters.Action.STEP_FORWARD)
        else:
            self.direction = self.facing
            self.__avoid_obstacle(knowledge)

    def __rotate(self, expected_facing: characters.Facing) -> None:
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

    def __get_expected_facing(self, distance: int, is_move_vertical: bool) -> characters.Facing:
        if is_move_vertical:
            return characters.Facing.UP if distance < 0 else characters.Facing.DOWN
        else:
            return characters.Facing.LEFT if distance < 0 else characters.Facing.RIGHT

    def __can_move_forward(self, knowledge: characters.ChampionKnowledge) -> bool:
        next_tile_coords = self.position + self.facing.value
        return next_tile_coords in knowledge.visible_tiles.keys() \
               and knowledge.visible_tiles[next_tile_coords].type == 'land'

    def __avoid_obstacle(self, knowledge):
        if self.facing == self.direction:
            if self.__can_move_forward(knowledge):
                self.direction = None
                self.moved = False
                self.action_queue.put(characters.Action.STEP_FORWARD)
            else:
                self.moved = False
                self.action_queue.put(characters.Action.TURN_RIGHT)
        else:
            if self.moved:
                self.moved = False
                self.action_queue.put(characters.Action.TURN_LEFT)
            else:
                if self.__can_move_forward(knowledge):
                    self.moved = True
                    self.action_queue.put(characters.Action.STEP_FORWARD)
                else:
                    self.moved = False
                    self.action_queue.put(characters.Action.TURN_RIGHT)

    def __guard_area(self) -> None:
        self.action_queue.put(characters.Action.TURN_RIGHT)

    def __calc_coords_diff(self, end_coords: int, start_coords: int) -> int:
        coords_dif = coordinates.sub_coords(end_coords, start_coords)
        return coords_dif

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
    TupTupController('Bot'),
]
