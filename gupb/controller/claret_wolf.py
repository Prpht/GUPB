import pygame
from enum import Enum
from collections import defaultdict
import random

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles


class Move(Enum):
    UP = coordinates.Coords(0, -1)
    LEFT = coordinates.Coords(-1, 0)
    RIGHT = coordinates.Coords(1, 0)
    DO_NOTHING = coordinates.Coords(0, 0) #ATTACK

#DOWN to add in future

POSSIBLE_MOVES = [
    Move.LEFT,
    Move.RIGHT,
    Move.UP,
    Move.DO_NOTHING
]

MIST_DESCRIPTOR = "mist"
WALL_DESCRIPTOR = "wall"
SEA_DESCRIPTOR = "sea"
MENHIR_DESCRIPTOR = "menhir"
KNIFE_DESCRIPTOR = "knife"
AXE_DESCRIPTOR = "axe"
BOW_DESCRIPTOR = "bow"
SWORD_DESCRIPTOR = "sword"
AMULET_DESCRIPTOR = "amulet"

INVALID_Q_VALUE = -1000000
MAX_PUNISHMENT = -50
DANGEROUS_DIST = 1500
EXPLORATION_PROB = 0.3
alpha = 0.5
gamma = 0
epsilon = 0.1

'''q_values: state - vector(coordinates.Coords) from bot position to nearest mist tile and action(Move) - move is defined in POSSIBLE_MOVES
  mapping_on_actions: map Move to Action'''
class ClaretWolfController:
    def __init__(self):
        self.last_observed_mist_vec: coordinates.Coords = None
        self.q_values: dict[(coordinates.Coords, Move), int] = defaultdict(int)
        self.mapping_on_actions: dict[Move, characters.Action] = {Move.UP: characters.Action.STEP_FORWARD,
                                                                  Move.LEFT: characters.Action.TURN_LEFT,
                                                                  Move.RIGHT: characters.Action.TURN_RIGHT,
                                                                  Move.DO_NOTHING: characters.Action.ATTACK, #ATTACK
                                                                  }

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ClaretWolfController):
            return True
        return False

    def __hash__(self) -> int:
        return 47

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        mist_vector = self.find_vector_to_nearest_mist_tile(knowledge)
        action: characters.Action = self.choose_next_step(knowledge, mist_vector)
        return action

    @property
    def name(self) -> str:
        return 'ClaretWolfController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN

    def find_vector_to_nearest_mist_tile(self, knowledge: characters.ChampionKnowledge):
        my_position: coordinates.Coords = knowledge.position
        mist_tiles: dict[coordinates.Coords, int] = defaultdict(int) #dict for storing distance to each mist tile from current bot position
        visible_tiles = knowledge.visible_tiles
        fun_distance = lambda my_p, mist_p: ((mist_p[0] - my_p[0]) ** 2 + (mist_p[1] - my_p[1]) ** 2)
        for coord in visible_tiles.keys():
            if self.is_given_type_tile(knowledge, coord, MIST_DESCRIPTOR):
                dist = fun_distance(my_position, coord)
                mist_tiles[coord] = dist

        if len(mist_tiles) > 0:
            min_dist_tuple = min(mist_tiles, key=mist_tiles.get)
            min_dist_vec = coordinates.Coords(min_dist_tuple[0], min_dist_tuple[1])
            self.last_observed_mist_vec = (min_dist_vec - my_position)
            return self.last_observed_mist_vec
        return None

    def is_given_type_tile(self, knowledge: characters.ChampionKnowledge, tile_coords: coordinates.Coords, descriptor):
        if tile_coords in knowledge.visible_tiles:
            tile_desc: tiles.TileDescription = knowledge.visible_tiles[tile_coords]
            for effect_desc in tile_desc.effects:
                if effect_desc.type == descriptor:
                    return True
        return False

    def choose_next_step(self, knowledge: characters.ChampionKnowledge, mist_vector: coordinates.Coords) -> characters.Action:
        best_new_move = random.choice(POSSIBLE_MOVES)
        if mist_vector is None and self.last_observed_mist_vec is None:
            return self.get_mapping_on_action(best_new_move)
        elif mist_vector is None:
            mist_vector = self.last_observed_mist_vec
        max_q_value = INVALID_Q_VALUE
        for next_coord in POSSIBLE_MOVES:
            next_position = (knowledge.position + next_coord.value)
            max_q_value_next_step = self.get_max_q_value_from_next_step(next_position)
            current_q_value: int = self.q_values[(mist_vector, next_coord)]
            reward = self.get_reward(knowledge, next_position, mist_vector)
            q_value = (1-alpha)*current_q_value + alpha*(reward + gamma*max_q_value_next_step)
            self.q_values[(knowledge.position, next_coord)] = q_value
            if q_value > max_q_value:
                max_q_value = q_value
                best_new_move = next_coord
        if random.uniform(0,1) < EXPLORATION_PROB:
            best_new_move = random.choice(POSSIBLE_MOVES)
        return self.get_mapping_on_action(best_new_move)

    def get_mapping_on_action(self, move: Move):
        return self.mapping_on_actions[move]

    def get_max_q_value_from_next_step(self, next_bot_position: coordinates.Coords):
        max_gain_next_step = INVALID_Q_VALUE
        best_new_move = None
        for next_coord in POSSIBLE_MOVES:
            max_q_value_next_step: int = self.q_values[(next_bot_position, next_coord)]
            if max_q_value_next_step > max_gain_next_step:
                max_gain_next_step = max_q_value_next_step

        return max_gain_next_step

    def get_reward(self, knowledge: characters.ChampionKnowledge, next_coord: coordinates.Coords, mist_vector: coordinates.Coords):
        mist_vec_dist = mist_vector[0]*mist_vector[0] + mist_vector[1]*mist_vector[1]
        if mist_vec_dist < DANGEROUS_DIST:
            return -50
        elif self.is_given_type_tile(knowledge, next_coord, WALL_DESCRIPTOR):
            return -8
        elif self.is_given_type_tile(knowledge, next_coord, SEA_DESCRIPTOR):
            return -5
        elif self.is_given_type_tile(knowledge, next_coord, MENHIR_DESCRIPTOR):
            return 0
        else :
            return 1


POTENTIAL_CONTROLLERS = [
    ClaretWolfController(),
]