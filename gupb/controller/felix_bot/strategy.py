import random
import math
import time
from gupb.model import coordinates, tiles
from typing import Dict
from .astar import Astar
from gupb.model.coordinates import Coords
from gupb.model.tiles import TileDescription
import random
from gupb.model.weapons import WeaponDescription

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model.arenas import Arena


WEAPON_RANGE = {
    'bow_loaded': 50,
    'sword': 3,
    'knife': 1
}


SAFE_POS = {
    'fisher_island': [
        Coords(12, 39),
        Coords(30, 4),
        Coords(9, 7)
    ],
    'isolated_shrine': [
        Coords(6, 6),
        Coords(6, 12),
        Coords(12, 6),
        Coords(12, 12)
    ],
    'archipelago': [
        Coords(7, 40),
        Coords(30, 42),
        Coords(45, 23),
        Coords(31, 8)
    ],
    'dungeon': [
        Coords(27, 24),
        Coords(22, 24),
        Coords(36, 21),
        Coords(48, 21),
        Coords(36, 37),
        Coords(36, 21),
        Coords(31, 16),
        Coords(18, 16),
        Coords(27, 14),
        Coords(14, 16),
        Coords(14, 9),
        Coords(14, 12),
        Coords(10, 12)
    ],
    'wasteland': [
        Coords(25, 13),
        Coords(27, 13),
        Coords(36, 33),
        Coords(6, 5),
        Coords(43, 5),
        Coords(44, 46)
    ]
}

class Strategy:
    def __init__(self):
        self.action_queue = []
        self.current_weapon = 'knife'
        self.facing = None  # inicjalizacja przy pierwszym decide
        self.position = None  # inicjalizacja przy pierwszym decide
        self.menhir_coord: coordinates.Coords = None
        self.grid = {}
        self.reached_menhir = False
        self.is_mist_coming = False
        # self.turning_direction = characters.Action.TURN_LEFT
        # self.turning_state_on = False
        self.explored_tiles = set()
        self.reached_safe_place = False
        self.banned_coords = []
        self.safe_place = None
        self.random_coord = None
        self.visible_tile_enemies = []
        self.arena_description = None

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.current_weapon = 'knife'
        self.action_queue = []
        self.reached_menhir = False
        self.is_mist_coming = False
        self.reached_safe_place = False
        self.explored_tiles = set()
        self.menhir_coord = None
        self.visible_tile_enemies = []
        self.arena_description = arena_description.name
        self.safe_place = None
        # self.safe_place = SAFE_PLACES[arena_description.name]
        for x_index in range(50):
            for y_index in range(50):
                self.grid[Coords(x_index, y_index)] = TileDescription(type='land', loot=None, character=None,
                                                                      effects=[])
        for coord, tile in Arena.load(arena_description.name).terrain.items():
            if tile.loot is not None:
                self.grid[coord] = TileDescription(type=tile.__class__.__name__.lower(), loot=WeaponDescription(name=tile.loot.description().name), character=None, effects=[])
                # print(tile.loot.description().name)
            else:
                self.grid[coord] = TileDescription(type=tile.__class__.__name__.lower(),
                                                   loot=None,
                                                   character=None, effects=[])


    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        pass

    def get_nearest_enemy_tile_coord(self):
        tile_coord = None
        smallest_distance = 1000
        for coord in self.visible_tile_enemies:
            distance = self.get_distance(coord)
            if distance < smallest_distance:
                smallest_distance = distance
                tile_coord = coord
        return tile_coord

    def get_safe_place(self):
        tile_coord = None
        smallest_distance = 1000
        for coord in SAFE_POS[self.arena_description]:
            distance = self.get_distance(coord)
            if distance < smallest_distance:
                smallest_distance = distance
                tile_coord = coord
        return tile_coord

    def random_action_choice(self):
        if self.__is_allowed_action(characters.Action.STEP_FORWARD):
            return characters.Action.STEP_FORWARD
        else:
            return characters.Action.TURN_LEFT

    def refresh_info(self, knowledge: characters.ChampionKnowledge):
        self.position = knowledge.position
        character = knowledge.visible_tiles[self.position].character
        self.facing = character.facing
        if self.current_weapon != character.weapon.name:
            self.action_queue = []
            self.safe_place = None
            self.grid[self.position] = TileDescription(type='land', loot=WeaponDescription(name=self.current_weapon), character=character, effects=[])
        self.current_weapon = character.weapon.name
        self.grid.update(knowledge.visible_tiles)
        self.explored_tiles.update(set(knowledge.visible_tiles.keys()))
        self.reached_menhir = False
        self.visible_tile_enemies = []
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

            if tile.character is not None and coord != self.position:
                self.visible_tile_enemies.append(coord)
        if self.random_coord in self.explored_tiles:
            self.random_coord = None
            self.action_queue = []

    def get_far_coord_orthogonal_to_tile(self, tile_coord, max_distance):
        coords = [tile_coord]
        distance = 0
        for i in range(1, max_distance):
            try:
                new_coord = coordinates.add_coords(tile_coord, Coords(i, 0))
                if self.grid[new_coord].type == 'wall':
                    break
                if i > distance and self.grid[new_coord].type == 'land':
                    distance = i
                    coords = [new_coord]
                if i == distance and self.grid[new_coord].type == 'land':
                    coords.append(new_coord)
            except KeyError:
                pass
        for i in range(1, max_distance):
            try:
                new_coord = coordinates.sub_coords(tile_coord, Coords(i, 0))
                if self.grid[new_coord].type == 'wall':
                    break
                if i > distance and self.grid[new_coord].type == 'land':
                    distance = i
                    coords = [new_coord]
                if i == distance and self.grid[new_coord].type == 'land':
                    coords.append(new_coord)
            except KeyError:
                pass
        for i in range(1, max_distance):
            try:
                new_coord = coordinates.add_coords(tile_coord, Coords(0, i))
                if self.grid[new_coord].type == 'wall':
                    break
                if i > distance and self.grid[new_coord].type == 'land':
                    distance = i
                    coords = [new_coord]
                if i == distance and self.grid[new_coord].type == 'land':
                    coords.append(new_coord)
            except KeyError:
                pass
        for i in range(1, max_distance):
            try:
                new_coord = coordinates.sub_coords(tile_coord, Coords(0, i))
                if self.grid[new_coord].type == 'wall':
                    break
                if i > distance and self.grid[new_coord].type == 'land':
                    distance = i
                    coords = [new_coord]
                if i == distance and self.grid[new_coord].type == 'land':
                    coords.append(new_coord)
            except KeyError:
                pass
                # kafelek nie byl widoczny
        tile_coord = None
        smallest_distance = 1000
        for coord in coords:
            distance = self.get_distance(coord)
            if distance < smallest_distance:
                smallest_distance = distance
                tile_coord = coord
        return tile_coord

    def can_attack(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
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

    def should_reload(self):
        return self.current_weapon == 'bow_unloaded'

    def validate_action_queue(self):
        if len(self.action_queue) > 0:
            if not self.__is_allowed_action(self.action_queue[0]):
                self.action_queue = []
                self.safe_place = None

    def __is_allowed_action(self, action):
        return not (action is characters.Action.STEP_FORWARD and self.grid[self.position + self.facing.value].type in [
            'wall', 'sea'] and 'mist' not in [effect.type for effect in self.grid[self.position + self.facing.value].effects])

    def get_weapon_coordinate(self, weapons_names):
        weapon_coord = None
        weapon_distance = 10000000
        for coord, tile in self.grid.items():
            if tile.loot is not None and tile.loot.name in weapons_names and coord not in self.banned_coords:
                distance = self.get_distance(coord)
                if distance < weapon_distance:
                    weapon_distance = distance
                    weapon_coord = coord
        return weapon_coord

    def get_random_passable_coord(self):
        available_tiles = set([coord for coord, tile in self.grid.items() if
                               tile.type == 'land' and 'mist' not in [effect.type for effect in tile.effects]])
        return random.choice(tuple(available_tiles - self.explored_tiles))

    def get_distance(self, coord):
        return abs(self.position[0] - coord[0]) + abs(self.position[1] - coord[1])

    def generate_queue_from_path(self, path):
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

    # def change_turning_direction(self):
    #     if self.turning_direction == characters.Action.TURN_LEFT:
    #         return characters.Action.TURN_RIGHT
    #     else:
    #         return characters.Action.TURN_LEFT
    #
    # def get_turning_direction(self, knowledge):
    #     # look for field with distance 1.0 -> field bot is looking at
    #     for i in knowledge.visible_tiles:
    #         x_diff = i[0] - knowledge.position[0]
    #         y_diff = i[1] - knowledge.position[1]
    #         distance = math.sqrt(x_diff * x_diff + y_diff * y_diff)
    #         if distance >= 0.9 and distance < 1.1:
    #             field_front_of_bot = knowledge.visible_tiles[i][0]
    #             if field_front_of_bot == "land":
    #                 # turn on turning state
    #                 self.turning_state_on = True
    #             if field_front_of_bot == "wall" and self.turning_state_on:
    #                 # change turning direction if bot see wall
    #                 turning = self.change_turning_direction()
    #                 self.turning_direction = turning
    #     return self.turning_direction
