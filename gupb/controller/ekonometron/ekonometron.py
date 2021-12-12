# created by Michał Kędra and Jan Proniewicz

"""
It's a bit confused but it's got a spirit
"""

import random
from typing import Tuple, Optional, Dict

from .outer_utils import *
from .specific_strategies import TryingMyBest, LetsHide, KillThemAll
from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.model.tiles import TileDescription
from gupb.model.profiling import profile


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class EkonometronController(controller.Controller):
    epsilon = 0.2

    # weapons_priorities = {
    #     "knife": 1,
    #     "amulet": 2,
    #     "axe": 3,
    #     "sword": 4,
    #     "bow_unloaded": 5,
    #     "bow_loaded": 5
    # }

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        # knowledge about the direction the controller is facing
        self.starting_coords: Optional[coordinates.Coords] = None
        self.direction: Optional[Facing] = None
        self.starting_combination = [characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]
        # arena data
        self.tiles_memory: Dict[coordinates.Coords, TileDescription] = {}
        self.forbidden_coords = None
        self.map_graphs = {}
        self.current_graph = None
        # knowledge about the weapon the bot is currently holding
        self.hold_weapon: str = "knife"
        # the path to destination our bot is supposed to follow after it's been found
        self.current_path: list = []
        self.destination: Optional[coordinates.Coords] = None
        self.camp_init: bool = False
        # strategies
        self.map_strategies = {}
        self.chosen_strategy = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EkonometronController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.starting_coords = None
        self.direction = None
        self.starting_combination = [characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]
        # getting arena map
        self.forbidden_coords = FORBIDDEN_COORDS[arena_description.name]
        arena = arenas.Arena.load(arena_description.name)
        for k, v in arena.terrain.items():
            if k not in self.forbidden_coords:
                self.tiles_memory[k] = v.description()
        if arena_description.name not in self.map_graphs:
            self.map_graphs[arena_description.name] = self.find_edges()
        self.current_graph = self.map_graphs[arena_description.name]
        self.hold_weapon = "knife"
        self.current_path = []
        self.destination = None
        self.camp_init = False
        # choosing the strategy
        if arena_description.name not in self.map_strategies:
            self.map_strategies[arena_description.name] = [TryingMyBest(self), LetsHide(self), KillThemAll(self)]
        strategies_list = self.map_strategies[arena_description.name]
        random_no = random.uniform(0, 1)
        if random_no > self.epsilon:
            self.chosen_strategy = max(strategies_list, key=lambda s: s.value)
        else:
            self.chosen_strategy = random.choice(strategies_list)

    @profile
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # if bot holds an unloaded bow
        if self.hold_weapon == "bow_unloaded":
            self.hold_weapon = "bow_loaded"
            return characters.Action.ATTACK
        # update bot's memory, based on the visible tiles
        visible_tiles = knowledge.visible_tiles
        self.update_memory(visible_tiles)
        # when bot doesn't know which direction it is facing
        if self.starting_coords is None:
            self.starting_coords = knowledge.position
            return forward_action(self, knowledge.position)
        if self.direction is None:
            dir_set = self.set_direction(knowledge.position)
            if not dir_set:
                return forward_action(self, knowledge.position, self.starting_combination.pop(0))
        # when bot is aware which direction it is facing
        return self.chosen_strategy.proceed(knowledge)

    def find_edges(self):
        """Finding edges for vertexes"""
        vertexes = []
        for coord, tile in self.tiles_memory.items():
            if tile.type == 'land' or tile.type == 'menhir':
                vertexes.append(coord)

        vertexes_edges = {}

        def check_if_next_to(vertex1, vertex2):
            if vertex1[0] == vertex2[0]:
                if (vertex1[1] - 1 == vertex2[1]) or (vertex1[1] + 1 == vertex2[1]):
                    return True
            elif vertex1[1] == vertex2[1]:
                if (vertex1[0] - 1 == vertex2[0]) or (vertex1[0] + 1 == vertex2[0]):
                    return True
            return False

        for ver in vertexes:
            vertex_edges = []
            for ver2 in vertexes:
                if ver != ver2 and check_if_next_to(ver, ver2):
                    vertex_edges.append(ver2)
            vertexes_edges[ver] = vertex_edges

        return vertexes_edges

    def set_direction(self, position):
        if self.starting_coords != position:
            coords_diff = position - self.starting_coords
            if coords_diff.x != 0:
                if coords_diff.x > 0:
                    self.direction = Facing.RIGHT
                else:
                    self.direction = Facing.LEFT
            elif coords_diff.y > 0:
                self.direction = Facing.DOWN
            else:
                self.direction = Facing.UP
            return True
        else:
            return False

    def update_memory(self, visible_tiles: Dict[coordinates.Coords, TileDescription]):
        for coords, tile_desc in visible_tiles.items():
            if coords not in self.forbidden_coords:
                self.tiles_memory[coords] = tile_desc

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN

    def praise(self, score: int) -> None:
        self.chosen_strategy.update_value(score)
        self.chosen_strategy.reset_mode()


POTENTIAL_CONTROLLERS = [
    EkonometronController("Ekonometron"),
]
