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


class Axis(Enum):
    HORIZONTAL = 0
    VERTICAL = 1


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



SIGHT_RANGE = 3000
DANGEROUS_DIST = 1500
LONG_SEQ = 6
EXPLORATION_PROB = 0.1
alpha = 0.5
gamma = 0
epsilon = 0.1

g_distance = lambda my_p, ref_p: ((ref_p[0] - my_p[0]) ** 2 + (ref_p[1] - my_p[1]) ** 2)
g_distance_vec = lambda vec: ((vec[0]) ** 2 + (vec[1]) ** 2)


class ClaretWolfController:
    def __init__(self):
        self.last_observed_mist_vec: coordinates.Coords = None
        self.bot_position = None
        self.run_seq_step = 0
        self.position_axis: Axis= None
        self.is_bot_in_rotation = False
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
        self.set_bot_axis_from_his_facing(knowledge)
        mist_vector = self.find_vector_to_nearest_mist_tile(knowledge)
        action: characters.Action = self.choose_next_step(knowledge, mist_vector)
        return action

    @property
    def name(self) -> str:
        return 'ClaretWolfController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN

    def set_bot_axis_from_his_facing(self, knowledge: characters.ChampionKnowledge):
        tile_descr: tiles.TileDescription =  knowledge.visible_tiles[self.bot_position]
        facing: characters.Facing = tile_descr.character.facing
        self.position_axis = Axis.HORIZONTAL if (facing == characters.Facing.LEFT or facing == characters.Facing.RIGHT)\
                             else Axis.VERTICAL



    def is_bot_safe(self, mist_vector: coordinates.Coords):
        return g_distance(self.bot_position, mist_vector) < DANGEROUS_DIST


    def find_vector_to_nearest_mist_tile(self, knowledge: characters.ChampionKnowledge):
        #my_position: coordinates.Coords = knowledge.position
        mist_tiles: dict[coordinates.Coords, int] = defaultdict(int) #dict for storing distance to each mist tile from current bot position
        visible_tiles = knowledge.visible_tiles

        for coord in visible_tiles.keys():
            if g_distance(self.bot_position, coord) <= SIGHT_RANGE and self.is_given_type_tile(knowledge, coord, MIST_DESCRIPTOR):
                dist = g_distance(self.bot_position, coord)
                mist_tiles[coord] = dist

        if len(mist_tiles) > 0:
            min_dist_tuple = min(mist_tiles, key=mist_tiles.get)
            min_dist_coord = coordinates.Coords(min_dist_tuple[0], min_dist_tuple[1])
            min_dist_vec = (min_dist_coord - self.bot_position)
            if self.last_observed_mist_vec is None:
                self.last_observed_mist_vec = min_dist_vec
                self.run_seq_step = 1
            elif g_distance_vec(min_dist_vec) < g_distance_vec(self.last_observed_mist_vec):
                print("RPY:: MIN_VEC_MIST = ", min_dist_vec)
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
        #elif self.is_bot_safe(mist_vector) and random.uniform(0, 1) < EXPLORATION_PROB:
        #   return self.explore_map()
        else:
            return self.run_away_from_mist()


    def run_away_from_mist(self):
        if self.run_seq_step == 1:
            self.run_seq_step += 1
            if self.is_mist_closer_from_left(): #closer from left
                return self.mapping_on_actions[Move.RIGHT]
            elif self.is_mist_closer_from_right():
                return self.mapping_on_actions[Move.LEFT]
            else: # mist directly in front of bot
                self.is_bot_in_rotation = True
                return self.mapping_on_actions[Move.RIGHT]
        elif self.is_bot_in_rotation: #continue rotation
            self.run_seq_step += 2
            self.is_bot_in_rotation = False
            return self.mapping_on_actions[Move.RIGHT]
        elif self.run_seq_step > 1 and self.run_seq_step < LONG_SEQ:
            self.run_seq_step += 1
            return self.mapping_on_actions[Move.UP]
        else:
            return self.mapping_on_actions[random.choice([Move.UP, Move.UP, Move.RIGHT, Move.LEFT, Move.UP])]

    def is_mist_closer_from_left(self):
        (self.position_axis == Axis.VERTICAL and \
        (self.last_observed_mist_vec[0] * self.last_observed_mist_vec[1] < 0)) \
        or (self.position_axis == Axis.HORIZONTAL and \
        (self.last_observed_mist_vec[0] * self.last_observed_mist_vec[1] > 0))

    def is_mist_closer_from_right(self):
        (self.position_axis == Axis.VERTICAL and \
        (self.last_observed_mist_vec[0] * self.last_observed_mist_vec[1] > 0)) \
        or (self.position_axis == Axis.HORIZONTAL and \
        (self.last_observed_mist_vec[0] * self.last_observed_mist_vec[1] < 0))


    def get_mapping_on_action(self, move: Move):
        return self.mapping_on_actions[move]


    def explore_map(self):
        return self.mapping_on_actions[random.choice([Move.UP, Move.UP, Move.RIGHT, Move.LEFT, Move.UP])]


POTENTIAL_CONTROLLERS = [
    ClaretWolfController(),
]