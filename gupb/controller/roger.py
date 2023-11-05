import random
import os
from enum import Enum
from typing import Dict, Tuple, Optional, List, NamedTuple

from pathfinding.core.grid import Grid
from pathfinding.core.node import GridNode
from pathfinding.finder.a_star import AStarFinder

from gupb import controller
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.arenas import TILE_ENCODING, WEAPON_ENCODING, Arena, Terrain
from gupb.model.coordinates import Coords, add_coords
from gupb.model.tiles import Land, Menhir

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


class SeenWeapon(NamedTuple):
    name: str
    seen_epoch_nr: int


class States(Enum):
    RANDOM_WALK     = 1
    HEAD_TO_WEAPON  = 2
    HEAD_TO_MENHIR  = 3
    FINAL_DEFENCE   = 4
    HEAD_TO_CENTER  = 5
    HEAD_TO_POTION  = 6

class WeaponValue(Enum):
    AMULET          = 0
    KNIFE           = 1
    AXE             = 3
    SWORD           = 5
    BOW_UNLOADED    = 6
    BOW_LOADED      = 7


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Roger(controller.Controller):
    def __init__(self, _id: str):
        self._id = _id
        self.current_position: Optional[coordinates.Coords] = None
        # remembering map
        self.epoch: int = 0
        self.seen_tiles: Dict[coordinates.Coords, Tuple[tiles.TileDescription, int]] = {}
        self.terrain: Optional[Terrain] = None
        self.arena_size = (50, 50)

        # pathfinding
        self.grid: Optional[Grid] = None
        self.finder = AStarFinder()

        self.menhir_coords: Optional[coordinates.Coords] = None
        self.weapons_coords: Dict[coordinates.Coords, SeenWeapon] = {}
        self.potion_coords: Optional[coordinates.Coords] = None

        self.actions_iterator = 0
        self.actions = []
        self.current_state = States.RANDOM_WALK
        self.beginning_iterator = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Roger):
            return self._id == other._id
        return False

    def __hash__(self) -> int:
        return hash(self._id)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.update_state(knowledge)
        match self.current_state:
            case States.RANDOM_WALK:
                return self.random_walk()
            case States.HEAD_TO_WEAPON:
                return self.head_to_weapon([])
            case States.HEAD_TO_MENHIR:
                return self.head_to_menhir([])
            case States.FINAL_DEFENCE:
                return self.final_defence()
            case States.HEAD_TO_CENTER:
                return self.head_to_center([])
            case States.HEAD_TO_POTION:
                return self.head_to_potion([])

    def get_path(self, dest: Coords) -> List[GridNode]:
        self.build_grid()
        x, y = self.current_position
        x_dest, y_dest = dest
        finder = AStarFinder()
        path, _ = finder.find_path(self.grid.node(x, y), self.grid.node(x_dest, y_dest), self.grid)
        return path

    def random_walk(self, omit_finish_search=False) -> characters.Action:
        coords = self.find_nearest_mist_coords(self.find_mist())
        if coords and not omit_finish_search:
            distance_squared = (coords.x - self.current_position.x) ** 2 + (coords.y - self.current_position.y) ** 2
            if distance_squared < 64:
                return self.head_to_finish()
        if self.potion_coords:
            path = self.get_path(self.potion_coords)
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_POTION
                return self.head_to_potion(path)
        if self.weapons_coords and not omit_finish_search:
            best_weapon_coords = self.get_current_best_weapon_coords()
            if best_weapon_coords:
                path = self.get_path(best_weapon_coords)
                if path:
                    self.actions = None
                    self.actions_iterator = 0
                    self.current_state = States.HEAD_TO_WEAPON
                    return self.head_to_weapon(path)

        return self.explore_map()

    def get_current_best_weapon_coords(self) -> Optional[Coords]:
        if self.current_weapon().name == "bow_unloaded" or self.current_weapon().name == "bow_loaded":
            return None
        sorted_weapon_coords = sorted(self.weapons_coords.keys(), key=lambda coords: self.get_distance(Coords(coords[0], coords[1]), self.current_position))
        nearest_weapon_coords = sorted_weapon_coords[0]
        if WeaponValue[self.current_weapon().name.upper()].value < WeaponValue[self.weapons_coords[nearest_weapon_coords].name.upper()].value:
            if nearest_weapon_coords != self.current_position:
                return nearest_weapon_coords
            else:
                return None
        return None

    def chose_next_tile(self) -> Coords:
        walkable = list(filter(lambda x: isinstance(x[1], Land) or isinstance(x[1], Menhir), self.terrain.items()))
        walkable_coords = set(map(lambda x: x[0], walkable))
        seen_coords = set(self.seen_tiles.keys())
        unseen_coords = walkable_coords - seen_coords
        unseen_coords = list(unseen_coords)
        best_coords = random.choices(list(walkable_coords), k=1)[0]
        if unseen_coords:
            k = min(10, len(unseen_coords))
            random_unseen = random.choices(unseen_coords, k=k)
        else:
            return best_coords
        longest_path_len = 0
        for coords in random_unseen:
            path = self.get_path(coords)
            if path:
                path_len = len(self.map_path_to_action_list(self.current_position, path))
                if path_len > longest_path_len:
                    longest_path_len = path_len
                    best_coords = coords
        return best_coords

    def explore_map(self):
        if self.actions and self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0

        if not self.actions:
            new_aim = self.chose_next_tile()
            path = self.get_path(new_aim)
            actions = self.map_path_to_action_list(self.current_position, path)
            self.actions = actions
            self.actions_iterator = 0
        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def return_attack_if_enemy_in_cut_range(self, action: characters.Action):
        if not action == characters.Action.ATTACK:
            cut_positions = self.get_weapon_cut_positions(self.current_weapon().name)
            for cut_position in cut_positions:
                if self.seen_tiles.get(cut_position):
                    if self.seen_tiles[cut_position][1] == self.epoch and self.seen_tiles[cut_position][0].character:
                        self.actions_iterator -= 1
                        return characters.Action.ATTACK
        return action
    def get_weapon_cut_positions(self, name: str) -> List[Coords]:
        initial_facing = self.seen_tiles[self.current_position][0].character.facing
        if name == 'knife':
            return self.get_line_cut_positions(initial_facing, 1)
        elif name == 'sword':
            return self.get_line_cut_positions(initial_facing, 3)
        elif name == 'bow_unloaded' or name == 'bow_loaded':
            return self.get_line_cut_positions(initial_facing, 50)
        elif name == 'axe':
            centre_position = self.current_position + initial_facing.value
            left_position = centre_position + initial_facing.turn_left().value
            right_position = centre_position + initial_facing.turn_right().value
            return [left_position, centre_position, right_position]
        elif name == 'amulet':
            position = self.current_position
            return [
                Coords(*position + (1, 1)),
                Coords(*position + (-1, 1)),
                Coords(*position + (1, -1)),
                Coords(*position + (-1, -1)),
                Coords(*position + (2, 2)),
                Coords(*position + (-2, 2)),
                Coords(*position + (2, -2)),
                Coords(*position + (-2, -2)),
            ]
        else:
            return []

    def get_line_cut_positions(self, initial_facing, reach):
        cut_positions = []
        cut_position = self.current_position
        for _ in range(reach):
            cut_position += initial_facing.value
            if cut_position not in self.terrain:
                break
            cut_positions.append(cut_position)
        return cut_positions

    # def return_attack_if_enemy_on_the_road(self, action: characters.Action):
    #     if action == characters.Action.STEP_FORWARD:
    #         action = self.return_attack_if_enemy_ahead(action)
    #     return action

    def head_to_finish(self) -> characters.Action:
        if self.menhir_coords:
            path = self.get_path(self.menhir_coords)
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_MENHIR
                return self.head_to_menhir(path)
        else:
            path = self.get_path(Coords(9, 9))
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_CENTER
                return self.head_to_center(path)

        self.current_state = States.RANDOM_WALK
        return self.random_walk(omit_finish_search=True)

    def get_distance(self, coords1, coords2):
        return ((coords1.x - coords2.x) ** 2 + (coords1.y - coords2.y) ** 2) ** 0.5

    def head_to_weapon(self, path: List[GridNode]) -> characters.Action:
        coords = self.find_nearest_mist_coords(self.find_mist())
        if coords:
            distance_squared = (coords.x - self.current_position.x) ** 2 + (coords.y - self.current_position.y) ** 2
            if distance_squared < 64:
                self.actions = None
                self.actions_iterator = 0
                return self.head_to_finish()
        if self.potion_coords:
            path = self.get_path(self.potion_coords)
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_POTION
                return self.head_to_potion(path)
        if not self.actions:
            self.actions = self.map_path_to_action_list(self.current_position, path)
        if self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0
            self.current_state = States.RANDOM_WALK
            return self.random_walk()

        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def head_to_menhir(self, path: List[GridNode]) -> characters.Action:
        if not self.actions:
            self.actions = self.map_path_to_action_list(self.current_position, path)
        if self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0
            self.current_state = States.FINAL_DEFENCE
            return self.final_defence()

        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def final_defence(self) -> characters.Action:
        self.actions = [characters.Action.TURN_RIGHT, characters.Action.ATTACK]
        action = self.actions[self.actions_iterator % 2]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def head_to_center(self, path) -> characters.Action:
        if not self.actions:
            self.actions = self.map_path_to_action_list(self.current_position, path)
        if self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0
            self.current_state = States.FINAL_DEFENCE
            return self.final_defence()

        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        return action

    def head_to_potion(self, path: List[GridNode]) -> characters.Action:
        if not self.actions:
            self.actions = self.map_path_to_action_list(self.current_position, path)
        if self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0
            self.potion_coords = None
            self.current_state = States.RANDOM_WALK
            return self.random_walk()

        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def update_state(self, knowledge: characters.ChampionKnowledge):
        self.epoch += 1
        self.current_position = knowledge.position
        self.seen_tiles.update(dict((Coords(x[0][0], x[0][1]), (x[1], self.epoch)) for x in knowledge.visible_tiles.items()))
        self.look_for_potion(knowledge.visible_tiles)
        if not self.menhir_coords:
            self.look_for_menhir(knowledge.visible_tiles)
        self.look_for_weapons(knowledge.visible_tiles)

    def map_path_to_action_list(self, current_position: Coords, path: List[GridNode]) -> List[characters.Action]:
        initial_facing = self.seen_tiles[current_position][0].character.facing
        facings: List[characters.Facing] = list(
            map(lambda a: characters.Facing(Coords(a[1].x - a[0].x, a[1].y - a[0].y)), list(zip(path[:-1], path[1:]))))
        actions: List[characters.Action] = []
        for a, b in zip([initial_facing, *facings[:-1]], facings):
            actions.extend(self.map_facings_to_actions(a, b))
        return actions

    def map_facings_to_actions(self, f1: characters.Facing, f2: characters.Facing) -> List[characters.Action]:
        if f1 == f2:
            return [characters.Action.STEP_FORWARD]
        elif f1.turn_left() == f2:
            return [characters.Action.TURN_LEFT, characters.Action.STEP_FORWARD]
        elif f1.turn_right() == f2:
            return [characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]
        else:
            return [characters.Action.TURN_RIGHT, characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        # reset round unique variables
        self.epoch = 0
        self.actions = None
        self.actions_iterator = 0
        self.seen_tiles = {}
        self.current_state = States.RANDOM_WALK
        self.menhir_coords = None
        self.weapons_coords = {}
        self.load_arena(arena_description.name)
        self.potion_coords = None

    def load_arena(self, name: str):
        terrain = dict()
        arena_file_path = os.path.join('resources', 'arenas', f'{name}.gupb')
        with open(arena_file_path) as file:
            for y, line in enumerate(file.readlines()):
                for x, character in enumerate(line):
                    if character != '\n':
                        position = coordinates.Coords(x, y)
                        if character in TILE_ENCODING:
                            terrain[position] = TILE_ENCODING[character]()
                        elif character in WEAPON_ENCODING:
                            terrain[position] = tiles.Land()
                            terrain[position].loot = WEAPON_ENCODING[character]()
        self.terrain = terrain
        x_size, y_size = max(terrain)
        self.arena_size = (x_size+1, y_size+1)

    def build_grid(self):
        def extract_walkable_tiles():
            try:
                return list(filter(lambda x: isinstance(x[1], Land) or isinstance(x[1], Menhir), self.terrain.items()))
            except AttributeError:
                return list(filter(lambda x: x[1][0].type == 'land' or x[1][0].type == 'menhir', self.seen_tiles.items()))

        walkable_tiles_list = extract_walkable_tiles()
        walkable_tiles_matrix = [[0 for y in range(self.arena_size[1])] for x in range(self.arena_size[0])]

        for tile in walkable_tiles_list:
            x, y = tile[0]
            walkable_tiles_matrix[y][x] = 1

        self.grid = Grid(self.arena_size[0], self.arena_size[1], walkable_tiles_matrix)

    def look_for_menhir(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, tile in tiles.items():
            if tile.type == 'menhir':
                self.menhir_coords = coords
                break

    def look_for_potion(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, tile in tiles.items():
            if tile.consumable:
                if tile.consumable.name == 'potion':
                    self.potion_coords = coords
                    return
        self.potion_coords = None

    def look_for_weapons(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, tile in tiles.items():
            if self.weapons_coords.get(coords):
                self._update_weapon(coords, tile)
            if tile.loot:
                self._add_weapon(coords, tile)

    def _add_weapon(self, coords, tile):
        self.weapons_coords[coords] = SeenWeapon(tile.loot.name, self.epoch)

    def _update_weapon(self, coords, tile):
        if not tile.loot:
            del self.weapons_coords[coords]

    def find_mist(self) -> List[coordinates.Coords]:
        mist_coords = []
        for coords, tile in self.seen_tiles.items():
            for effect in tile[0].effects:
                if effect.type == 'mist':
                    mist_coords.append(coords)
        return mist_coords

    def find_nearest_mist_coords(self, mist_coords: List[coordinates.Coords]) -> Optional[coordinates.Coords]:
        min_distance_squared = 2 * self.arena_size[0] ** 2
        nearest_mist_coords = None
        for coords in mist_coords:
            distance_squared = (coords.x - self.current_position.x) ** 2 + (coords.y - self.current_position.y) ** 2
            if distance_squared < min_distance_squared:
                min_distance_squared = distance_squared
                nearest_mist_coords = coords
        return nearest_mist_coords

    def current_weapon(self):
        return self.seen_tiles[self.current_position][0].character.weapon

    @property
    def name(self) -> str:
        return f'Roger_{self._id}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED


POTENTIAL_CONTROLLERS = [
    Roger('1'),
]
