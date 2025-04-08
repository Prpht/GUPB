import random
from typing import List, Dict, NamedTuple, Tuple

from gupb.model import coordinates
from gupb.model.tiles import Tile
from gupb.model import tiles
from gupb.controller.pirat.menhir_finder import MenhirFinder
from gupb.controller.pirat.menhir_finder2 import MenhirFinder2

from gupb.controller.pirat.pathfinding import PathFinder

from gupb import controller
from gupb.model import arenas
from gupb.model.arenas import ArenaDescription, Arena
from gupb.model import characters
from gupb.controller.pirat.menhir_finder import MenhirFinder
import random


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.ATTACK,
    characters.Action.DO_NOTHING,
]

PREDEFINE_POSSIBILITEIS = {
    frozenset({(1, 0), (0, -1), (0, 1)}): "E",
    frozenset({(-1, 0), (0, -1), (0, 1)}): "W",
    frozenset({(0, 1), (-1, 0), (1, 0)}): "S",
    frozenset({(0, -1), (-1, 0), (1, 0)}): "N"
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class PiratController(controller.Controller):

    def __init__(self, first_name: str, threeshold = 0, reset = None, dynamic_reg = False, region_size = 5, rand_turn = 0):
        self.first_name: str = first_name
        self.menhir_finder = None

        print("init")
        self.arena: Arena = None
        self.weapons: dict[str, characters.Weapon] = {}
        self.actual_path: List[Tile] = []
        self.region_size = region_size
        self.dynamic_reg = dynamic_reg
        self.hero = None
        self.threeshold = threeshold
        self.i = 0
        self.res = reset
        self.rand_turn = rand_turn

    def __eq__(self, other: object) -> bool:
        print("eq")
        if isinstance(other, PiratController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)
    
    def update_info(self, knowledge: characters.ChampionKnowledge) -> None:
        hero: characters.ChampionDescription = knowledge.visible_tiles[knowledge.position].character
        self.hero = hero


    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        #menhir_position = self.menhir_finder.update(knowledge) -> twoje

        self.update_info(knowledge)
        self.i += 1
        try:
            if self.menhir_finder.menhir is None:
                self.menhir_finder.look_for_menhir(knowledge.visible_tiles)
                if self.res != None and self.i % self.res == 0:
                    self.actual_path = []

                if len(self.actual_path) < self.threeshold:
                    self.actual_path = []

                if self.actual_path:
                    if random.random() < self.rand_turn:
                        return characters.Action.TURN_LEFT
                    return self._move_along_path(knowledge)
                else:
                    reg = self.menhir_finder.get_max_probability_region()
                    end = self.get_first_standable_tile(reg)
                    start = knowledge.position
                    self.actual_path = self.path_finder.find_the_shortest_path(start, end)
            else:
                return self._move_towards_menhir(knowledge)

        except Exception as e:
            print(f"{e}")
            self.actual_path = []            
        
        return random.choice(POSSIBLE_ACTIONS)
    
    
    def _move_along_path(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        next_coord = self.actual_path[0]
        delta_x = next_coord.x - knowledge.position.x
        delta_y = next_coord.y - knowledge.position.y
        delta = coordinates.Coords(delta_x, delta_y)  

        if delta == (0, 0):
            self.actual_path.pop(0)
            if not self.actual_path:
                return random.choice(POSSIBLE_ACTIONS)
            next_coord = self.actual_path[0]
            delta_x = next_coord.x - knowledge.position.x
            delta_y = next_coord.y - knowledge.position.y
            delta = coordinates.Coords(delta_x, delta_y)

        if delta == self.hero.facing.value:
            if not self.actual_path:
                self.current_target = None
            return characters.Action.STEP_FORWARD
        elif delta == self.hero.facing.turn_left().value:
            return characters.Action.STEP_LEFT
        elif delta == self.hero.facing.turn_right().value:
            return characters.Action.STEP_RIGHT
        else:

            return characters.Action.TURN_LEFT


    def _move_towards_menhir(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        
        if not self.actual_path:
            start = knowledge.position
            end = self.menhir_finder.menhir  
            self.actual_path = self.path_finder.find_the_shortest_path(start, end)

        return self._move_along_path(knowledge)


    def praise(self, score: int) -> None:
        print("praise")
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        print("reset")
        self.menhir_finder = MenhirFinder(arena_description)
        print("reset")
        self.arena = arenas.Arena.load(arena_description.name)
        self.menhir_finder = MenhirFinder2(arena=self.arena)
        self.path_finder = PathFinder(arena=self.arena)
        self.actual_path = []
        if self.dynamic_reg:
            self.region_size = self.arena.size[0] // 5
        pass

    def get_info_about_map(self, arena: Arena) -> None:
        for coord in arena.terrain:
            tile = arena.terrain[coord]
            description = tile.description()
            if description.type == "menhir":
                self.menhir = coord
                continue

            if not tile.passable or tile.character or tile.consumable:
                self.pos_wthout_menhir.add(coord)

    def look_for_menhir(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription] ) -> None:
        for coord, tile in visible_tiles.items():
            if tile.type == "menhir":
                print(f"Found menhir at {coord}")
                self.menhir = coord
                break
            else:
                self.pos_wthout_menhir.add(coord)
        a = self.all_pos - self.pos_wthout_menhir


    def get_first_standable_tile(self, region: Tuple[int, int]) -> coordinates.Coords:
        x_start = region[0] * self.region_size
        y_start = region[1] * self.region_size
        x_end = x_start + self.region_size
        y_end = y_start + self.region_size

        for x in range(x_start, x_end):
            for y in range(y_start, y_end):
                pos = coordinates.Coords(x, y)
                if self.arena.terrain[pos].terrain_passable():
                    return pos
        return None
    

    @property
    def name(self) -> str:
        return f"PiratController{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PIRAT
    
"""
    
def get_shortest_path(arena: List[List[Tile]], start: characters.Coords, end: characters.Coords) -> list[characters.Coords]:
    Get the shortest path from start to end.
    # This is a placeholder implementation.
    # In a real implementation, you would use a pathfinding algorithm like A* or Dijkstra's.
    

    return [start, end]

def get_arena_from_string(arena_string: str) -> List[List[Tile]]:
    Convert a string representation of an arena into a list of lists of tiles.
    # This is a placeholder implementation.
    # In a real implementation, you would parse the string and create the appropriate Tile objects.

    return [[Tile() for _ in range(10)] for _ in range(10)]

"""

POTENTIAL_CONTROLLERS = [
    PiratController("Pirat"),
]
