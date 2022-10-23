import random
from math import sqrt
import numpy as np
from numpy import empty, sqrt, square
from scipy.linalg import lstsq
from xmlrpc.client import Boolean

from gupb import controller
from gupb.model import arenas
from gupb.model import characters, effects
from gupb.model import coordinates
from gupb.model import tiles
from gupb.model.arenas import Arena, ArenaDescription

from gupb.controller.tuptus.map import Map
from gupb.controller.tuptus.pathfinder import Pathfinder

from typing import Optional, List



""" 
    @TODO:
        1) Cleanup in decide method
        2) Move information from Controller to Map class

"""



POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class TuptusController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.map: Map = Map()
        self.pathfinder: Pathfinder = Pathfinder(self.map)
        self.facing: Optional[characters.Facing] = None
        self.planned_actions: Optional[List] = None
        self.menhir_coords = None
        self.mist_tiles = np.array([])
        self.mist_directions: List[Optional[characters.Facing]] = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TuptusController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.planned_actions:
            return self.planned_actions.pop(0)
        

        self.map.decode_knowledge(knowledge)
        self.find_facing_direction(knowledge.position, knowledge.visible_tiles.keys())
        if not self.menhir_coords:
            self.menhir_coords = self.is_menhir(knowledge.visible_tiles)


        if self.map.weapons_position and not self.is_mist_bool(knowledge.visible_tiles):

            for name, pos in self.map.weapons_position.items():
                weapon_pos = pos
                weapon_name = name
            del self.map.weapons_position[weapon_name]
            self._raw_path = self.pathfinder.astar(knowledge.position, weapon_pos)
            
            if self._raw_path:
                if len(self._raw_path) > 1:
                    self.planned_actions = self.pathfinder.plan_path(self._raw_path, self.facing)
                    self._raw_path = None
                    return self.planned_actions.pop(0)

        next_block_position = knowledge.position + self.facing.value
        next_block = knowledge.visible_tiles[next_block_position]        
        if next_block.type in ["wall", "sea"]: 
            choice = POSSIBLE_ACTIONS[random.randint(0,1)]
        elif self.is_mist_bool(knowledge.visible_tiles) > 0:
            if self.menhir_coords:
                self._raw_path = self.pathfinder.astar(knowledge.position, self.menhir_coords)
                if self._raw_path:
                    self.planned_actions = self.pathfinder.plan_path(self._raw_path, self.facing)
                    return self.planned_actions.pop(0)

            self.mist_directions.append(self.facing)
            if self.facing == characters.Facing.UP and characters.Facing.RIGHT in self.mist_directions:
                choice = POSSIBLE_ACTIONS[1]
            elif self.facing == characters.Facing.UP and characters.Facing.LEFT in self.mist_directions:
                choice = POSSIBLE_ACTIONS[0]
            elif self.facing == characters.Facing.DOWN and characters.Facing.RIGHT in self.mist_directions:
                choice = POSSIBLE_ACTIONS[0]
            elif self.facing == characters.Facing.DOWN and characters.Facing.LEFT in self.mist_directions:
                choice = POSSIBLE_ACTIONS[1]
            elif self.facing == characters.Facing.RIGHT and characters.Facing.UP in self.mist_directions:
                choice = POSSIBLE_ACTIONS[1]
            elif self.facing == characters.Facing.RIGHT and characters.Facing.DOWN in self.mist_directions:
                choice = POSSIBLE_ACTIONS[0]
            elif self.facing == characters.Facing.LEFT and characters.Facing.UP in self.mist_directions:
                choice = POSSIBLE_ACTIONS[0]
            elif self.facing == characters.Facing.LEFT and characters.Facing.DOWN in self.mist_directions:
                choice = POSSIBLE_ACTIONS[1]
            else:
                choice = POSSIBLE_ACTIONS[1]
        elif next_block.character and (knowledge.visible_tiles[knowledge.position].character.health >= next_block.character.health):
            choice = POSSIBLE_ACTIONS[3]
        elif next_block.character and (knowledge.visible_tiles[knowledge.position].character.health < next_block.character.health) and not (self.are_opposite(next_block.character.facing, self.facing)):
            choice = POSSIBLE_ACTIONS[3]
        elif next_block.character and (knowledge.visible_tiles[knowledge.position].character.health < next_block.character.health):
            choice = POSSIBLE_ACTIONS[random.randint(0,1)]
        else:
            choice = POSSIBLE_ACTIONS[2]
        return choice

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.facing = None
        self.mist_tiles = np.array([])
        self.mist_directions = []
        self.map.weapons_position = {}
        self.planned_actions = None
        self._raw_path = None


    def find_facing_direction(self, position, visible_tiles_positions) -> None:
        facing_dct = {(0, -1): characters.Facing.UP,
                      (0, 1): characters.Facing.DOWN,
                      (-1, 0): characters.Facing.LEFT,
                      (1, 0): characters.Facing.RIGHT}

        x_pos, y_pos = position

        for x_tile, y_tile in visible_tiles_positions:
            difference = (x_tile - x_pos, y_tile - y_pos)

            if difference in facing_dct.keys():
                self.facing = facing_dct[difference]
                break
    
    def is_mist(self, visible_tiles) -> list:
        for coords, tile in visible_tiles.items():
            if effects.EffectDescription(type='mist') in tile.effects:
                if len(self.mist_tiles)==0:
                    self.mist_tiles = np.array(np.array(coords))
                elif np.array(coords) not in self.mist_tiles:
                    self.mist_tiles = np.vstack((self.mist_tiles, np.array(np.array(coords))))  
                self.map.tuptable_map[coords] = 1

        return self.mist_tiles
    
    def are_opposite(self, opponent_facing, character_facing):
        opposites = [(characters.Facing.UP, characters.Facing.DOWN),
        (characters.Facing.DOWN, characters.Facing.UP),
        (characters.Facing.LEFT, characters.Facing.RIGHT),
        (characters.Facing.RIGHT, characters.Facing.LEFT)]
        if (opponent_facing, character_facing) in opposites:
            return True
        return False


    def is_mist_bool(self, visible_tiles) -> bool:
        for tile in visible_tiles.values():
            if effects.EffectDescription(type='mist') in tile.effects:
                return True  
        return False
    
    def is_menhir(self, visible_tiles):
        for coords, tile in visible_tiles.items():
            if  tile == tiles.Menhir:
                return coords 
        return None




    @property
    def name(self) -> str:
        return f'TuptusController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREEN


POTENTIAL_CONTROLLERS = [
    TuptusController("CiCik")
]
