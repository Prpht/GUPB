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
SIGHT_RANGE = 3000
LONG_SEQ = 5
SHORT_SEQ = 2
EXPLORATION_PROB = 0.3
alpha = 0.5
gamma = 0
epsilon = 0.1

g_distance = lambda my_p, ref_p: ((ref_p[0] - my_p[0]) ** 2 + (ref_p[1] - my_p[1]) ** 2)
g_distance_vec = lambda vec: ((vec[0]) ** 2 + (vec[1]) ** 2)


'''q_values: state - vector(coordinates.Coords) from bot position to nearest mist tile and action(Move) - move is defined in POSSIBLE_MOVES
  mapping_on_actions: map Move to Action'''
class ClaretWolfController:
    def __init__(self):
        self.last_observed_mist_vec: coordinates.Coords = None
        self.bot_position = None
        self.run_seq_step = 0
        self.min_dist_from_mist = 10e6
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
        self.bot_position = knowledge.position
        mist_vector = self.find_vector_to_nearest_mist_tile(knowledge)
        action: characters.Action = self.choose_next_step(knowledge, mist_vector)
        return action

    @property
    def name(self) -> str:
        return 'ClaretWolfController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN

    def is_bot_safe(self, mist_vector: coordinates.Coords):
        return g_distance(self.bot_position, mist_vector) < DANGEROUS_DIST


    def find_vector_to_nearest_mist_tile(self, knowledge: characters.ChampionKnowledge):
        my_position: coordinates.Coords = knowledge.position
        mist_tiles: dict[coordinates.Coords, int] = defaultdict(int) #dict for storing distance to each mist tile from current bot position
        visible_tiles = knowledge.visible_tiles

        for coord in visible_tiles.keys():
            if g_distance(self.bot_position, coord) <= SIGHT_RANGE and self.is_given_type_tile(knowledge, coord, MIST_DESCRIPTOR):
                dist = g_distance(my_position, coord)
                mist_tiles[coord] = dist

        if len(mist_tiles) > 0:
            min_dist_tuple = min(mist_tiles, key=mist_tiles.get)
            min_dist_coord = coordinates.Coords(min_dist_tuple[0], min_dist_tuple[1])
            min_dist_vec = (min_dist_coord - my_position)
            if self.last_observed_mist_vec is None:
                self.last_observed_mist_vec = min_dist_vec
                self.run_seq_step = 1
            elif g_distance_vec(min_dist_vec) < g_distance_vec(self.last_observed_mist_vec):
                self.last_observed_mist_vec = min_dist_vec
                if self.run_seq_step == LONG_SEQ:
                    self.run_seq_step = 1

        return self.last_observed_mist_vec


    def is_given_type_tile(self, knowledge: characters.ChampionKnowledge, tile_coords: coordinates.Coords, descriptor):
        if tile_coords in knowledge.visible_tiles:
            tile_desc: tiles.TileDescription = knowledge.visible_tiles[tile_coords]
            for effect_desc in tile_desc.effects:
                if effect_desc.type == descriptor:
                    return True
        return False


    def choose_next_step(self, knowledge: characters.ChampionKnowledge, mist_vector: coordinates.Coords) -> characters.Action:
        best_new_move = random.choice(POSSIBLE_MOVES)
        #if not self.is_bot_safe(mist_vector):
        if self.last_observed_mist_vec is None:
            return self.mapping_on_actions[best_new_move]
        else:
            return self.run_away_from_mist()


    def run_away_from_mist(self):
        if self.run_seq_step == 1:
            self.run_seq_step += 1
            if self.last_observed_mist_vec[0] > 0: #closer from left, x coord > 0
                return self.mapping_on_actions[Move.RIGHT]
            else:
                return self.mapping_on_actions[Move.LEFT]
        elif self.run_seq_step > 1 and self.run_seq_step < LONG_SEQ:
            self.run_seq_step += 1
            return self.mapping_on_actions[Move.UP]
        else:
            return self.mapping_on_actions[random.choice([Move.UP, Move.RIGHT, Move.LEFT, Move.UP])]


    def get_mapping_on_action(self, move: Move):
        return self.mapping_on_actions[move]


POTENTIAL_CONTROLLERS = [
    ClaretWolfController(),
]