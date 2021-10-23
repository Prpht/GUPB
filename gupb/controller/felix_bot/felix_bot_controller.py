import random
import math
import time
from gupb.model import coordinates, tiles
from typing import Dict
from .astar import Astar
from gupb.model.coordinates import Coords
from gupb.model.tiles import TileDescription

from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
]

WEAPON_RANGE = {
    'bow_loaded': 50,
    'sword': 3,
    'knife': 1
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class FelixBotController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.action_queue = []
        self.current_weapon = 'knife'
        self.facing = None  # inicjalizacja przy pierwszym decide
        self.position = None  # inicjalizacja przy pierwszym decide
        self.menhir_coord: coordinates.Coords = None
        self.grid = {}
        self.reached_menhir = False
        self.is_mist_coming = False
        self.turning_direction = characters.Action.TURN_LEFT
        self.turning_state_on = False

        for x_index in range(200):
            for y_index in range(200):
                self.grid[Coords(x_index, y_index)] = TileDescription(type='land', loot=None, character=None,
                                                                      effects=[])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FelixBotController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.current_weapon = 'knife'
        self.action_queue = []
        self.reached_menhir = False
        self.is_mist_coming = False

    def change_turning_direction(self):
        if self.turning_direction == characters.Action.TURN_LEFT:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_LEFT

    def get_turning_direction(self, knowledge):
        # look for field with distance 1.0 -> field bot is looking at
        for i in knowledge.visible_tiles:
            x_diff = i[0] - knowledge.position[0]
            y_diff = i[1] - knowledge.position[1]
            distance = math.sqrt(x_diff * x_diff + y_diff * y_diff)
            if distance >= 0.9 and distance < 1.1:
                field_front_of_bot = knowledge.visible_tiles[i][0]
                if field_front_of_bot == "land":
                    # turn on turning state
                    self.turning_state_on = True
                if field_front_of_bot == "wall" and self.turning_state_on:
                    # change turning direction if bot see wall
                    turning = self.change_turning_direction()
                    self.turning_direction = turning
        return self.turning_direction

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.__refresh_info(knowledge)

        if self.__can_attack(knowledge.visible_tiles) or self.__should_reload():
            return characters.Action.ATTACK

        if len(self.action_queue) == 0:
            if not self.is_mist_coming and self.current_weapon not in ['axe']:
                weapon_coord = self.__get_weapon_coordinate(['axe'])
                if weapon_coord is not None:
                    path = Astar.astar(self.grid, self.position, weapon_coord)
                    if path is not None:
                        self.action_queue = self.__generate_queue_from_path(
                            path)
            elif not self.is_mist_coming and self.current_weapon in ['axe']:
                path = Astar.astar(self.grid, self.position, Coords(6, 6))
                if len(path) == 0:
                    return self.get_turning_direction(knowledge)
                if path is not None:
                    self.action_queue = self.__generate_queue_from_path(
                        path)
            elif self.is_mist_coming and self.menhir_coord is not None and not self.reached_menhir:
                path = Astar.astar(self.grid, self.position, self.menhir_coord)
                if path is not None:
                    self.action_queue = self.__generate_queue_from_path(
                        path)

        self.__validate_action_queue()

        if len(self.action_queue) > 0:
            return self.action_queue.pop(0)
        elif self.reached_menhir and self.is_mist_coming:
            return characters.Action.TURN_LEFT
        else:
            return random.choice([characters.Action.TURN_LEFT,
                                  characters.Action.TURN_RIGHT,
                                  characters.Action.STEP_FORWARD])

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED

    def __refresh_info(self, knowledge: characters.ChampionKnowledge):
        self.position = knowledge.position
        character = knowledge.visible_tiles[self.position].character
        self.facing = character.facing
        self.current_weapon = character.weapon.name
        self.grid.update(knowledge.visible_tiles)
        for coord, tile in knowledge.visible_tiles.items():
            if self.menhir_coord is None and tile.type == 'menhir':
                self.menhir_coord = coord
            if not self.is_mist_coming:
                for effect in tile.effects:
                    if effect.type == 'mist':
                        self.is_mist_coming = True
                        self.action_queue = []  # reset queue since mist appeared
            if tile.type == 'menhir' and self.position == coord:
                self.reached_menhir = True

    def __can_attack(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
        try:
            if self.current_weapon == 'axe':
                centre_position = self.position + self.facing.value
                left_position = centre_position + self.facing.turn_left().value
                right_position = centre_position + self.facing.turn_right().value
                cut_positions = [left_position, centre_position, right_position]
                for cut_position in cut_positions:
                    if visible_tiles[cut_position].character:
                        return True
            elif self.current_weapon == 'amulet':
                centre_position = self.position + self.facing.value
                left_position = centre_position + self.facing.turn_left().value
                right_position = centre_position + self.facing.turn_right().value
                cut_positions = [left_position, right_position]
                for cut_position in cut_positions:
                    if visible_tiles[cut_position].character:
                        return True
            elif self.current_weapon == 'bow_loaded' or self.current_weapon == 'sword' or self.current_weapon == 'knife':
                reach = WEAPON_RANGE[self.current_weapon]
                tile = self.position
                for _ in range(1, reach + 1):
                    tile = tile + self.facing.value
                    if visible_tiles[tile].character:
                        return True
        except KeyError:
            # kafelek nie byl widoczny
            return False
        return False

    def __should_reload(self):
        return self.current_weapon == 'bow_unloaded'

    def __validate_action_queue(self):
        if len(self.action_queue) > 0:
            if not self.__is_allowed_action(self.action_queue[0]):
                self.action_queue = []

    def __is_allowed_action(self, action):
        return not (action is characters.Action.STEP_FORWARD and self.grid[self.position + self.facing.value].type in [
            'wall', 'sea'])

    def __get_weapon_coordinate(self, weapons_names):
        weapon_coord = None
        weapon_distance = 10000000
        for coord, tile in self.grid.items():
            if tile.loot is not None and tile.loot.name in weapons_names:
                distance = self.__get_distance(coord)
                if distance < weapon_distance:
                    weapon_distance = distance
                    weapon_coord = coord
        return weapon_coord

    def __get_distance(self, coord):
        return abs(self.position[0] - coord[0]) + abs(self.position[1] - coord[1])

    def __generate_queue_from_path(self, path):
        queue = []
        current_cord = self.position
        current_facing = self.facing
        while len(path) > 0:
            next_coord = path.pop(0)
            desired_facing = characters.Facing(coordinates.sub_coords(next_coord, current_cord))
            if (current_facing == Facing.RIGHT and desired_facing == Facing.DOWN) or (
                    current_facing == Facing.DOWN and desired_facing == Facing.LEFT) or (
                    current_facing == Facing.LEFT and desired_facing == Facing.UP) or (
                    current_facing == Facing.UP and desired_facing == Facing.RIGHT):
                queue.append(characters.Action.TURN_RIGHT)

            if (current_facing == Facing.RIGHT and desired_facing == Facing.UP) or (
                    current_facing == Facing.UP and desired_facing == Facing.LEFT) or (
                    current_facing == Facing.LEFT and desired_facing == Facing.DOWN) or (
                    current_facing == Facing.DOWN and desired_facing == Facing.RIGHT):
                queue.append(characters.Action.TURN_LEFT)

            if (current_facing == Facing.RIGHT and desired_facing == Facing.LEFT) or (
                    current_facing == Facing.UP and desired_facing == Facing.DOWN) or (
                    current_facing == Facing.LEFT and desired_facing == Facing.RIGHT) or (
                    current_facing == Facing.DOWN and desired_facing == Facing.UP):
                queue.append(characters.Action.TURN_LEFT)
                queue.append(characters.Action.TURN_LEFT)

            queue.append(characters.Action.STEP_FORWARD)

            current_cord = next_coord
            current_facing = desired_facing
        return queue
