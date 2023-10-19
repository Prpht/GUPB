import random
from typing import Dict, Tuple, Optional

from pathfinding.core.grid import Grid
from pathfinding.core.node import GridNode
from pathfinding.finder.a_star import AStarFinder

from gupb import controller
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters

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

        self._printed = False


    def __eq__(self, other: object) -> bool:
        if isinstance(other, OurController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.seen_tiles.update(dict((x[0], (x[1], self.epoch))for x in knowledge.visible_tiles.items()))
        self.epoch += 1
        self.build_grid()
        print(self.grid.grid_str())
        return random.choice(POSSIBLE_ACTIONS)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

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
