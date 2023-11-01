import random
from enum import Enum
from typing import Dict, Tuple, Optional, List, NamedTuple

from pathfinding.core.grid import Grid
from pathfinding.core.node import GridNode
from pathfinding.finder.a_star import AStarFinder

from gupb import controller
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.coordinates import Coords

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

MAX_SIZE = 20


class SeenWeapon(NamedTuple):
    name: str
    seen_epoch_nr: int


class States(Enum):
    RANDOM_WALK = 1
    HEAD_TO_WEAPON = 2
    HEAD_TO_MENHIR = 3
    FINAL_DEFENCE = 4
    HEAD_TO_CENTER = 5


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Roger(controller.Controller):
    def __init__(self, _id: str):
        self._id = _id
        self.current_position: Optional[coordinates.Coords] = None
        # remembering map
        self.epoch: int = 0
        self.seen_tiles: Dict[coordinates.Coords, Tuple[tiles.TileDescription, int]] = {}

        # pathfinding
        self.grid: Optional[Grid] = None
        self.finder = AStarFinder()

        self.menhir_coords: Optional[coordinates.Coords] = None
        self.weapons_coords: Dict[coordinates.Coords, SeenWeapon] = {}

        self.actions_iterator = 0
        self.actions = []
        self.current_state = States.RANDOM_WALK
        self.has_weapon = False
        self.beginning_iterator = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Roger):
            return self._id == other._id
        return False

    def __hash__(self) -> int:
        return hash(self._id)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:

        self.update_state(knowledge)
        if self.beginning_iterator < 4:
            self.beginning_iterator += 1
            return characters.Action.TURN_RIGHT
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
        if self.has_weapon and not omit_finish_search:
            return self.head_to_finish()
        if not self.has_weapon and self.weapons_coords and not omit_finish_search:
            path = self.get_path(list(self.weapons_coords.keys())[0])
            if path:
                self.current_state = States.HEAD_TO_WEAPON
                return self.head_to_weapon(path)

        return random.choices(POSSIBLE_ACTIONS[:-1], weights=[1, 1, 3])[0]

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

    def head_to_weapon(self, path: List[GridNode]) -> characters.Action:
        coords = self.find_nearest_mist_coords(self.find_mist())
        if coords:
            distance_squared = (coords.x - self.current_position.x) ** 2 + (coords.y - self.current_position.y) ** 2
            if distance_squared < 64:
                self.actions = None
                self.actions_iterator = 0
                return self.head_to_finish()
        if not self.actions:
            self.actions = self.map_path_to_action_list(self.current_position, path)
        if self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0
            # if not self.seen_tiles[self.current_position][0].character.weapon:
            #     return self.head_to_weapon()
            # else:
            self.has_weapon = True
            return self.head_to_finish()

        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
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
        return action

    def final_defence(self) -> characters.Action:
        self.actions = [characters.Action.TURN_RIGHT, characters.Action.ATTACK]
        action = self.actions[self.actions_iterator % 2]
        self.actions_iterator += 1
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

    def update_state(self, knowledge: characters.ChampionKnowledge):
        self.current_position = knowledge.position
        self.seen_tiles.update(dict((Coords(x[0][0], x[0][1]), (x[1], self.epoch)) for x in knowledge.visible_tiles.items()))
        self.epoch += 1

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
        self.has_weapon = False

    def build_grid(self):
        def extract_walkable_tiles():
            return list(filter(lambda x: x[1][0].type == 'land' or x[1][0].type == 'menhir', self.seen_tiles.items()))

        walkable_tiles_list = extract_walkable_tiles()
        walkable_tiles_matrix = [[0 for y in range(MAX_SIZE)] for x in range(MAX_SIZE)]

        for tile in walkable_tiles_list:
            x, y = tile[0]
            walkable_tiles_matrix[y][x] = 1

        self.grid = Grid(MAX_SIZE, MAX_SIZE, walkable_tiles_matrix)

    def look_for_menhir(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, tile in tiles.items():
            if tile.type == 'menhir':
                self.menhir_coords = coords
                break

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
        min_distance_squared = 2 * MAX_SIZE**2
        nearest_mist_coords = None
        for coords in mist_coords:
            distance_squared = (coords.x - self.current_position.x) ** 2 + (coords.y - self.current_position.y) ** 2
            if distance_squared < min_distance_squared:
                min_distance_squared = distance_squared
                nearest_mist_coords = coords
        return nearest_mist_coords

    @property
    def name(self) -> str:
        return f'Roger_{self._id}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED


POTENTIAL_CONTROLLERS = [
    Roger('1'),
]
