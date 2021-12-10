# created by Michał Kędra and Jan Proniewicz

"""
It's a bit confused but it's got a spirit
"""

import random
import numpy as np
import time
from typing import Tuple, Optional, Dict

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.model.tiles import TileDescription
from gupb.model.profiling import profile
from .behaviour_utils import *
from .draw_paths import *
from .specific_strategies import TryingMyBest, LetsHide, KillThemAll


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class EkonometronController(controller.Controller):
    epsilon = 0.2

    weapons_priorities = {
        "knife": 1,
        "amulet": 2,
        "axe": 3,
        "sword": 4,
        "bow_unloaded": 5,
        "bow_loaded": 5
    }

    line_weapons_reach = {
        "knife": 1,
        "sword": 3,
        "bow_loaded": 50
    }

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
        self.map_graphs = {}
        self.current_graph = None
        # knowledge about the weapon the bot is currently holding
        self.hold_weapon: str = "knife"
        # the path to destination our bot is supposed to follow after it's been found
        self.current_path: list = []
        self.destination: Optional[coordinates.Coords] = None
        self.menhir_visited: bool = False
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
        arena = arenas.Arena.load(arena_description.name)
        for k, v in arena.terrain.items():
            self.tiles_memory[k] = v.description()
        if arena_description.name not in self.map_graphs:
            self.map_graphs[arena_description.name] = self.find_edges()
        self.current_graph = self.map_graphs[arena_description.name]
        self.hold_weapon = "knife"
        self.current_path = []
        self.destination = None
        self.menhir_visited = False
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
        return self.chosen_strategy.proceed(knowledge)

    # @profile
    # def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
    #     # if bot holds an unloaded bow
    #     if self.hold_weapon == "bow_unloaded":
    #         self.hold_weapon = "bow_loaded"
    #         return characters.Action.ATTACK
    #     # update bot's memory, based on the visible tiles
    #     visible_tiles = knowledge.visible_tiles
    #     self.update_memory(visible_tiles)
    #     # save menhir position if visible
    #     if self.destination is None:
    #         save_menhir_position_if_visible(self, knowledge.visible_tiles)
    #     # when bot doesn't know which direction it is facing
    #     if self.starting_coords is None:
    #         self.starting_coords = knowledge.position
    #         return forward_action(self, knowledge.position)
    #     if self.direction is None:
    #         if self.starting_coords != knowledge.position:
    #             coords_diff = knowledge.position - self.starting_coords
    #             if coords_diff.x != 0:
    #                 if coords_diff.x > 0:
    #                     self.direction = Facing.RIGHT
    #                 else:
    #                     self.direction = Facing.LEFT
    #             elif coords_diff.y > 0:
    #                 self.direction = Facing.DOWN
    #             else:
    #                 self.direction = Facing.UP
    #         else:
    #             return forward_action(self, knowledge.position, self.starting_combination.pop(0))
    #
    #     # when bot is aware which direction it is facing
    #     # identify visible enemies
    #     if enemy_in_reach(self, knowledge):
    #         if self.hold_weapon == "bow_loaded":
    #             self.hold_weapon = "bow_unloaded"
    #         return characters.Action.ATTACK
    #     if self.menhir_visited:
    #         return characters.Action.TURN_RIGHT
    #
    #     # if moving to menhir
    #     if self.move_to_chosen_place:
    #         if move_all(self, knowledge.position):
    #             return forward_action(self, knowledge.position)
    #         else:
    #             self.direction = self.direction.turn_right()
    #             return characters.Action.TURN_RIGHT
    #
    #     # check if mist visible
    #     mist_incoming = check_if_mist_visible(knowledge.visible_tiles)
    #     # if mist, init run to menhir
    #     if not self.move_to_chosen_place and mist_incoming and not self.menhir_visited:
    #         self.current_path = bfs_shortest_path(self.current_graph, knowledge.position, self.destination)
    #         if self.current_path:
    #             self.current_path.pop(0)
    #             self.move_to_chosen_place = True
    #             if move_all(self, knowledge.position):
    #                 return forward_action(self, knowledge.position)
    #             else:
    #                 self.direction = self.direction.turn_right()
    #                 return characters.Action.TURN_RIGHT
    #
    #     # if bot uses the strategy3, try to remember if there were any enemies to your side
    #     if self.chosen_strategy == "strategy3":
    #         action = enemy_to_the_side(self, knowledge.position)
    #         if action != characters.Action.DO_NOTHING:
    #             return action
    #     # react to a weapon on the ground
    #     if weapon_in_reach(self, knowledge.position):
    #         action = react_to_weapon(self, knowledge.position)
    #         if action != characters.Action.DO_NOTHING:
    #             return action
    #     # turn if there is an obstacle in front
    #     if obstacle_in_front(self, knowledge.position):
    #         return take_a_turn(self, knowledge.position)
    #     # if there is nothing interesting going on, bot will move forward
    #     rand_gen = random.random()
    #     if rand_gen <= 0.9:
    #         return forward_action(self, knowledge.position)
    #     else:
    #         return take_a_turn(self, knowledge.position)

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

    def update_memory(self, visible_tiles: Dict[coordinates.Coords, TileDescription]):
        for coords, tile_desc in visible_tiles.items():
            self.tiles_memory[coords] = tile_desc

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN

    def praise(self, score: int) -> None:
        self.chosen_strategy.update_value(score)


POTENTIAL_CONTROLLERS = [
    EkonometronController("Ekonometron"),
]
