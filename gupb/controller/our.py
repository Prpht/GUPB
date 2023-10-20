import random
from typing import Dict, Tuple, Optional, List

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

# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class OurController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        # remembering map
        self.epoch: int = 0
        self.seen_tiles: Dict[coordinates.Coords, Tuple[tiles.TileDescription, int]] = {}

        # pathfinding
        self.grid: Optional[Grid] = None

        self.paths = {
            'to_menhir': None,
            'to_nearest_weapon': None
        }
        self.actions_iterator = 0
        self.actions = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OurController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.seen_tiles.update(dict((x[0], (x[1], self.epoch))for x in knowledge.visible_tiles.items()))
            self.epoch += 1
            self.build_grid()
            self.finder = AStarFinder()
            x, y = knowledge.position
            path = self.finder.find_path(self.grid.node(x, y), self.grid.node(6, 4), self.grid)
            if not self.actions:
                self.actions = self.map_path_to_action_list(knowledge.position, path[0])

            if self.actions and self.actions_iterator < len(self.actions):
                action = self.actions[self.actions_iterator]
                self.actions_iterator += 1
            else:
                action = random.choice(POSSIBLE_ACTIONS)
            print(self.actions)
        except Exception as e:
            print(e)
        return action
# naliczyć najkrótsze ścieżki po aktualizacji mapy oraz po dotarciu do punktu
# dict z najkrótszymi ścieżkami.

    def map_path_to_action_list(self, current_position: Coords, path: List[GridNode]) -> List[characters.Action]:
        initial_facing = self.seen_tiles[current_position][0].character.facing
        facings: List[characters.Facing] = list(map(lambda a: characters.Facing(Coords(a[1].x-a[0].x, a[1].y-a[0].y)), list(zip(path[:-1], path[1:]))))
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

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        print(arena_description) # dostajemy to także przed pierwszą turą - możemy zapamiętywać mapy między rozgrywkami po ich nazwie
        # reset roud unique variables
        self.epoch = 0
        self.actions = []
        self.actions_iterator = 0
        self.seen_tiles = {}

    def build_grid(self):
        def extract_walkable_tiles():
            return list(filter(lambda x: x[1][0].type == 'land', self.seen_tiles.items()))

        walkable_tiles_list = extract_walkable_tiles()
        walkable_tiles_matrix = [[0 for y in range(MAX_SIZE)] for x in range(MAX_SIZE)]

        for tile in walkable_tiles_list:
            x, y = tile[0]
            walkable_tiles_matrix[y][x] = 1
        try:
            self.grid = Grid(MAX_SIZE, MAX_SIZE, walkable_tiles_matrix)
        except Exception as e:
            print(e)


    @property
    def name(self) -> str:
        return f'OurController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    OurController("OOOOR"),
]
