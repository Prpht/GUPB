# created by Michał Kędra and Jan Proniewicz

"""
It's a bit confused but it's got a spirit
"""

import random
import numpy as np

from typing import Tuple, Optional, Dict

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.model.tiles import TileDescription
from gupb.model.profiling import profile
from behaviour_utils import *
from draw_paths import *


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class EkonometronController(controller.Controller):
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
        # bot tries to remember the tiles it has seen thus far
        self.tiles_memory: Dict[coordinates.Coords, TileDescription] = {}
        # knowledge about the weapon the bot is currently holding
        self.hold_weapon: str = "knife"
        # the mode our bot goes into after noticing the mist
        self.mist_incoming: bool = False
        self.move_to_chosen_place: bool = False
        self.actual_path: list = []
        self.menhir_position: Optional[coordinates.Coords] = None
        self.menhir_visited: bool = False
        # looking for a place to camp in
        self.move_to_hide = False
        self.camp_visited = False
        self.camp_position = False
        self.turns = 0
        self.only_attack = False
        # strategies
        self.epsilon = 0.2
        # trying_my_best - bot freely explores the map, it picks up whatever weapon it can and attacks enemies in sight
        # lets_hide - bot is looking for a specific spot on the map where it can 'camp' from
        # kill_them_all - bot checks for the enemies on the side so it can take them down faster
        self.strategy_values = {
            "trying_my_best": 0.0,
            "lets_hide": 0.0,
            "kill_them_all": 0.0
        }
        self.strategy_no = {
            "trying_my_best": 0,
            "lets_hide": 0,
            "kill_them_all": 0
        }
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
        self.tiles_memory = {}
        self.hold_weapon = "knife"
        self.mist_incoming = False
        self.move_to_chosen_place = False
        self.actual_path = []
        self.menhir_position = None
        self.menhir_visited = False
        self.move_to_hide = False
        self.camp_visited = False
        self.camp_position = False
        self.turns = 0
        self.only_attack = False
        # choosing the strategy
        random_no = random.uniform(0, 1)
        if random_no > self.epsilon:
            self.chosen_strategy = max(self.strategy_values, key=self.strategy_values.get)
        else:
            self.chosen_strategy = random.choice(list(self.strategy_values))
        #print(self.strategy_rewards)
        #print(self.chosen_strategy)

    @profile
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # if bot holds an unloaded bow
        if self.hold_weapon == "bow_unloaded":
            self.hold_weapon = "bow_loaded"
            return characters.Action.ATTACK
        # update bot's memory, based on the visible tiles
        visible_tiles = knowledge.visible_tiles
        self.update_memory(visible_tiles)
        # making graph
        visible_graph = find_edges(self)
        # save menhir position if visible
        if self.menhir_position is None:
            save_menhir_position_if_visible(self, knowledge.visible_tiles)

        # when bot doesn't know which direction it is facing
        if self.starting_coords is None:
            self.starting_coords = knowledge.position
            return forward_action(self, knowledge.position)
            #return characters.Action.STEP_FORWARD
        if self.direction is None:
            if self.starting_coords != knowledge.position:
                coords_diff = knowledge.position - self.starting_coords
                if coords_diff.x != 0:
                    if coords_diff.x > 0:
                        self.direction = Facing.RIGHT
                    else:
                        self.direction = Facing.LEFT
                elif coords_diff.y > 0:
                    self.direction = Facing.DOWN
                else:
                    self.direction = Facing.UP
            else:
                return forward_action(self, knowledge.position, self.starting_combination.pop(0))
                #return self.starting_combination.pop(0)

        # when bot is aware which direction it is facing
        # identify visible enemies
        if enemy_in_reach(self, knowledge):
            if self.hold_weapon == "bow_loaded":
                self.hold_weapon = "bow_unloaded"
            return characters.Action.ATTACK

        if self.menhir_visited:
            return characters.Action.TURN_RIGHT

        # if moving to menhir
        if self.move_to_chosen_place:
            if move_all(self, knowledge.position):
                return forward_action(self, knowledge.position)
                #return characters.Action.STEP_FORWARD
            else:
                self.direction = self.direction.turn_right()
                return characters.Action.TURN_RIGHT

        # check if mist visible
        check_if_mist_visible(self, knowledge.visible_tiles)
        # if mist, init run to menhir
        if not self.move_to_chosen_place and self.mist_incoming and not self.menhir_visited:
            self.actual_path = bfs_shortest_path(visible_graph, knowledge.position, self.menhir_position)
            if self.actual_path:
                self.actual_path.pop(0)
                self.move_to_chosen_place = True
                if move_all(self, knowledge.position):
                    return forward_action(self, knowledge.position)
                    #return characters.Action.STEP_FORWARD
                else:
                    self.direction = self.direction.turn_right()
                    return characters.Action.TURN_RIGHT

        if self.chosen_strategy == "strategy2":
            if not self.camp_position:
                save_camp_position_if_visible(self, knowledge.visible_tiles)
            if self.move_to_hide:
                if move_all_hide(self, knowledge.position):
                    return forward_action(self, knowledge.position)
                else:
                    self.direction = self.direction.turn_right()
                    return characters.Action.TURN_RIGHT
            if not self.move_to_hide and not self.camp_visited and self.camp_position:
                self.actual_path = bfs_shortest_path(visible_graph, knowledge.position, self.camp_position)
                if self.actual_path:
                    self.actual_path.pop(0)
                    self.move_to_hide = True
                    if move_all_hide(self, knowledge.position):
                        return forward_action(self, knowledge.position)
                    else:
                        self.direction = self.direction.turn_right()
                        return characters.Action.TURN_RIGHT
            if self.turns > 0 and self.only_attack:
                self.turns -= 1
                self.direction = self.direction.turn_right()
                return characters.Action.TURN_RIGHT
            if self.only_attack:
                return characters.Action.ATTACK

        # if bot uses the strategy3, try to remember if there were any enemies to your side
        if self.chosen_strategy == "strategy3":
            action = enemy_to_the_side(self, knowledge.position)
            if action != characters.Action.DO_NOTHING:
                return action
        # react to a weapon on the ground
        if weapon_in_reach(self, knowledge.position):
            action = react_to_weapon(self, knowledge.position)
            if action != characters.Action.DO_NOTHING:
                return action
        # turn if there is an obstacle in front
        if obstacle_in_front(self, knowledge.position):
            return take_a_turn(self, knowledge.position)
        # if there is nothing interesting going on, bot will move forward
        rand_gen = random.random()
        if rand_gen <= 0.9:
            return forward_action(self, knowledge.position)
            #return characters.Action.STEP_FORWARD
        else:
            return take_a_turn(self, knowledge.position)

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
        self.strategy_no[self.chosen_strategy] += 1
        self.strategy_values[self.chosen_strategy] += (score - self.strategy_values[self.chosen_strategy]) / \
                                                      self.strategy_no[self.chosen_strategy]


POTENTIAL_CONTROLLERS = [
    EkonometronController("Ekonometron"),
]
