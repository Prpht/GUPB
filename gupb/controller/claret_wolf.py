import pygame

from enum import Enum
from collections import defaultdict

import random
import copy

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles
from gupb.model import weapons

from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder


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

TERRAIN_DESCRIPTORS = {
    "mist": -1,
    "wall": -1,
    "sea": -1,
    "menhir": -1,
    "land":1
}

WEAPONS_DESCRIPTORS = {
    "bow": 40,
    "amulet": 30,
    "sword": 20,
    "axe": 20,
    "knife": 1
}

SIGHT_RANGE = 2000
DANGEROUS_DIST = 1500
LONG_SEQ = 6
EXPLORATION_PROB = 0.1
alpha = 0.5
gamma = 0
epsilon = 0.1

g_distance = lambda my_p, ref_p: ((ref_p[0] - my_p[0]) ** 2 + (ref_p[1] - my_p[1]) ** 2)
g_distance_vec = lambda vec: ((vec[0]) ** 2 + (vec[1]) ** 2)

counter = 0

class ClaretWolfController:
    def __init__(self):
        self.last_observed_mist_vec: coordinates.Coords = None
        self.weapon = "knife"
        self.weapons_knowledge = {}
        self.enemies_knowledge = {}
        self.dynamic_obsticles = {}
        self.arena = None
        self.bot_position = None
        self.facing = None
        self.enviroment_map = None
        self.bot_position = None
        self.menhir_position = None
        self.queue = []
        self.run_seq_step = 0
        self.position_axis: Axis= None
        self.is_bot_in_rotation = False
        self.mapping_on_actions: dict[Move, characters.Action] = {Move.UP: characters.Action.STEP_FORWARD,
                                                                  Move.LEFT: characters.Action.TURN_LEFT,
                                                                  Move.RIGHT: characters.Action.TURN_RIGHT,
                                                                  Move.DO_NOTHING: characters.Action.ATTACK,
                                                                  }

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ClaretWolfController):
            return True
        return False


    def __hash__(self) -> int:
        return 47


    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_position = arena_description.menhir_position
        self.init_enviroment_map(arena_description.name)


    def terrain_mapping(self, terrain, coords: coordinates.Coords)->int:
        field_type = (terrain[coords]).description().type.lower()
        return TERRAIN_DESCRIPTORS[field_type]


    def init_enviroment_map(self, map_name: str):
        arena = None
        try:
            arena_object = arenas.Arena.load(map_name)
            size = arena_object.size
            terrain = arena_object.terrain
            arena = [[self.terrain_mapping(terrain, coordinates.Coords(*(x,y))) for x in range(size[0])] for y in range(size[1])] 
            self.arena = arena
            self.enviroment_map = Grid(matrix=arena)
        except:
            pass


    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.update_bot(knowledge)
            self.update_weapons_knowledge(knowledge)
            global counter
            if (counter % 5) == 0:
                self.update_enemies_knowledge(knowledge)
                counter = 0
            counter += 1
            self.set_bot_axis_from_his_facing(knowledge)
            
            if self.has_next_defined():
                next_move = self.queue.pop(0)
                return next_move

            self.choose_next_step(knowledge)

            if self.has_next_defined():
                next_move = self.queue.pop(0)
                return next_move
            else:
                return self.explore_map()
        except Exception as e:
            #print("EXCEPTION CAUSE = ", e)
            return Action.DO_NOTHING
            pass


    def update_enemies_knowledge(self, knowledge):
        visible_tiles = knowledge.visible_tiles
        for coord, tile_desc in visible_tiles.items():
            if tile_desc.character is not None and coord != self.bot_position:
                self.enemies_knowledge[tile_desc.character.controller_name] = (tile_desc, coord)
            if tile_desc.character is not None and tile_desc.character.health == 0:
                del self.enemies_knowledge[tile_desc.character.controller_name]


    def check_enemies_in_neighbourhood(self):
        neighbourhood_distance = 1000000
        closest_alive_enemy = None
        min_distance_to_enemy = neighbourhood_distance
        for k, v in self.enemies_knowledge.items():
            if v[0].character.health > 0:
                distance = g_distance(self.bot_position, v[1])
                closest_alive_enemy = k if distance < min_distance_to_enemy else closest_alive_enemy
                min_distance_to_enemy = distance if distance < min_distance_to_enemy else min_distance_to_enemy


        target_position = self.enemies_knowledge[closest_alive_enemy][1] if closest_alive_enemy is not None else None #coord
        return target_position


    def has_next_defined(self):
        return len(self.queue) > 0


    def choose_next_step(self, knowledge: characters.ChampionKnowledge) -> None:

        # can we attack?
        if self.can_attack(knowledge):
            self.queue =[]
            self.queue.append(characters.Action.ATTACK)
            return

        # is mist a danger?
        if g_distance(self.bot_position, self.menhir_position) < 2:
            self.queue.append(self.recon())
            return
        else:
            self.find_vector_to_nearest_mist_tile(knowledge)
            if self.last_observed_mist_vec is not None:
                self.queue = []
                next = self.menhir_position
                if next:
                    self.enqueue_target(next)
                    if random.uniform(0, 1) < 0.3:
                        self.last_observed_mist_vec = None
                    return 
            
        # maybe look for new weapon?
        next = self.determine_next_weapon()
        if next:
            self.queue = []
            self.enqueue_target(next)
            return

        # maybe chase?
        next = self.check_enemies_in_neighbourhood()
        if next:
            self.queue = []
            self.enqueue_target(next)


        # maybe explore DEFAULT


    def enqueue_target(self, target):
        next_coords = self.go_to_coords(target)
        if len(next_coords) > 1:
            self.queue += self.move(self.facing, self.bot_position ,next_coords[-2])


    def can_attack(self, knowledge: characters.ChampionKnowledge):
        tiles_in_range = []
        position = self.bot_position
        if self.weapon == KNIFE_DESCRIPTOR:
            tiles_in_range = [position + self._mul(self.facing.value, i) for i in range(1, weapons.Knife.reach() + 1)]
        elif self.weapon == SWORD_DESCRIPTOR:
            tiles_in_range = [position + self._mul(self.facing.value, i) for i in range(1, weapons.Sword.reach() + 1)]
        elif self.weapon == BOW_DESCRIPTOR:
            tiles_in_range = [position + self._mul(self.facing.value, i) for i in range(1, weapons.Bow.reach() + 1)]
        elif self.weapon == AMULET_DESCRIPTOR:
            tiles_in_range = [position + (1, 1), position + (-1, 1), position + (1, -1), position + (-1, -1)]
        else:   
            centre_position = position + self.facing.value
            left_position = centre_position + self.facing.turn_left().value
            right_position = centre_position + self.facing.turn_right().value
            tiles_in_range =  [left_position, centre_position, right_position]
        enemies = self.get_enemies(knowledge)
        common_points = list(set(tiles_in_range) & set(enemies))
        return len(common_points) > 0


    def get_enemies(self, knowledge):
        enemies = dict(filter(lambda elem: elem[1].character != None and elem[0] != self.bot_position, knowledge.visible_tiles.items()))
        return list(enemies.keys())


    def _mul(self, coor, scalar: int):
        return coordinates.Coords(*(coor[0]*scalar, coor[1]*scalar))


    @property
    def name(self) -> str:
        return 'ClaretWolfController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN

    def update_bot(self, knowledge: characters.ChampionKnowledge):
        self.bot_position = knowledge.position
        self.weapon       = knowledge.visible_tiles[self.bot_position].character.weapon.name
        self.facing       = knowledge.visible_tiles[self.bot_position].character.facing


    def update_weapons_knowledge(self, knowledge: characters.ChampionKnowledge) -> None:
        weapons = dict(filter(lambda elem: elem[1].loot, knowledge.visible_tiles.items()))
        weapons = {k: v.loot.name for k, v in weapons.items()}
        for weapon in weapons.items():
            self.weapons_knowledge[weapon[0]] = weapon[1]
        self.dynamic_obstacles = copy.deepcopy(self.weapons_knowledge)
        self.weapons_knowledge = dict(filter(lambda elem: WEAPONS_DESCRIPTORS[elem[1]] > WEAPONS_DESCRIPTORS[self.weapon] and elem[0] != self.bot_position, self.weapons_knowledge.items()))
        self.dynamic_obstacles = dict(filter(lambda elem: WEAPONS_DESCRIPTORS[elem[1]] <= WEAPONS_DESCRIPTORS[self.weapon] and elem[0] != self.bot_position, self.dynamic_obstacles.items()))
        

    def determine_next_weapon(self):
        temp_weapons_knowledge = dict(filter(lambda elem: WEAPONS_DESCRIPTORS[elem[1]] > WEAPONS_DESCRIPTORS[self.weapon] and elem[1] != self.bot_position, self.weapons_knowledge.items()))
        weapons_scores = {k: 2*WEAPONS_DESCRIPTORS[v]/(1 + g_distance(self.bot_position, k)) for k, v in temp_weapons_knowledge.items()}
        if weapons_scores: 
            max_value = max(weapons_scores.values())
            max_keys = [k for k, v in weapons_scores.items() if v == max_value]
            return max_keys[0]
        return None


    def go_to_coords(self, target: coordinates.Coords):
        def create_grid():
            temp_arena = self.arena.copy()
            for w in self.dynamic_obstacles.keys():
                # print("UPDATING ARENA")
                # print(w)
                temp_arena[w[0]][w[1]] = -1
            return Grid(matrix=temp_arena)

        self.enviroment_map = create_grid()
        # self.enviroment_map.cleanup() #cleaning not required

        start = self.enviroment_map.node(target[0], target[1])
        end = self.enviroment_map.node(self.bot_position[0], self.bot_position[1])

        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        path, _ = finder.find_path(start, end, self.enviroment_map)
        return path


    def move(self, starting_facing: characters.Facing, bot: coordinates.Coords, target: coordinates.Coords):
        expected_direction = characters.Facing(coordinates.sub_coords(target, bot))
        facing_turning_left = starting_facing
        left_actions = []
        while facing_turning_left != expected_direction:
            facing_turning_left = facing_turning_left.turn_left()
            left_actions.append(characters.Action.TURN_LEFT)

        facing_turning_right = starting_facing
        right_actions = []
        while facing_turning_right != expected_direction:
            facing_turning_right = facing_turning_right.turn_right()
            right_actions.append(characters.Action.TURN_RIGHT)

        actions = right_actions if len(left_actions) > len(right_actions) else left_actions
        actions.append(characters.Action.STEP_FORWARD)
        return actions


    def set_bot_axis_from_his_facing(self, knowledge: characters.ChampionKnowledge):
        tile_descr: tiles.TileDescription =  knowledge.visible_tiles[self.bot_position]
        facing: characters.Facing = tile_descr.character.facing
        self.position_axis = Axis.HORIZONTAL if (facing == characters.Facing.LEFT or facing == characters.Facing.RIGHT)\
                             else Axis.VERTICAL


    # def is_bot_safe(self, mist_vector: coordinates.Coords):
    #     return g_distance(self.bot_position, mist_vector) < DANGEROUS_DIST


    def find_vector_to_nearest_mist_tile(self, knowledge: characters.ChampionKnowledge):
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

    # def run_away_from_mist(self):
        # print("BOT POSITION")
        # print(self.bot_position)
        # ret_val = self.go_to_coords(self.menhir_position)
        # print("RETURN TO MENHIR")
        # print(ret_val)
        # if g_distance(self.bot_position, self.menhir_position) < 2:
        #     return self.recon()
        # else:
        #     self.last_observed_mist_vec = None
        #     return self.menhir_position
        # if self.run_seq_step == 1:
        #     self.run_seq_step += 1
        #     if self.is_mist_closer_from_left(): #closer from left
        #         return self.mapping_on_actions[Move.RIGHT]
        #     elif self.is_mist_closer_from_right():
        #         return self.mapping_on_actions[Move.LEFT]
        #     else: # mist directly in front of bot
        #         self.is_bot_in_rotation = True
        #         return self.mapping_on_actions[Move.RIGHT]
        # elif self.is_bot_in_rotation: #continue rotation
        #     self.run_seq_step += 2
        #     self.is_bot_in_rotation = False
        #     return self.mapping_on_actions[Move.RIGHT]
        # elif self.run_seq_step > 1 and self.run_seq_step < LONG_SEQ:
        #     self.run_seq_step += 1
        #     return self.mapping_on_actions[Move.UP]
        # else:
        #     return self.mapping_on_actions[random.choice([Move.UP, Move.UP, Move.RIGHT, Move.LEFT, Move.UP])]

    def recon(self):
        return characters.Action.TURN_LEFT

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
        # TODO: Check if not going in eapons based on  bot state
        return self.mapping_on_actions[random.choice([Move.UP, Move.UP, Move.RIGHT, Move.LEFT, Move.UP])]


POTENTIAL_CONTROLLERS = [
    ClaretWolfController(),
]
