import math
import random
from abc import ABC, abstractmethod
from collections import defaultdict

import numpy as np
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.model import characters
from gupb.model import coordinates
from gupb.model.characters import Facing
from gupb.controller.bb8.qlearning import (calculate_state, learn_actions, 
                                           QAction, update_q_values)

PI = 4.0 * math.atan(1.0)

ROTATIONS = {
    (Facing.UP, Facing.RIGHT): characters.Action.TURN_RIGHT,
    (Facing.UP, Facing.DOWN): characters.Action.TURN_RIGHT,
    (Facing.UP, Facing.LEFT): characters.Action.TURN_LEFT,
    (Facing.RIGHT, Facing.UP): characters.Action.TURN_LEFT,
    (Facing.RIGHT, Facing.DOWN): characters.Action.TURN_RIGHT,
    (Facing.RIGHT, Facing.LEFT): characters.Action.TURN_RIGHT,
    (Facing.DOWN, Facing.UP): characters.Action.TURN_LEFT,
    (Facing.DOWN, Facing.RIGHT): characters.Action.TURN_LEFT,
    (Facing.DOWN, Facing.LEFT): characters.Action.TURN_RIGHT,
    (Facing.LEFT, Facing.UP): characters.Action.TURN_RIGHT,
    (Facing.LEFT, Facing.RIGHT): characters.Action.TURN_RIGHT,
    (Facing.LEFT, Facing.DOWN): characters.Action.TURN_LEFT
}  # in the form - current facing, desired facing

FACING_COORDS = {
    Facing.UP: (0, -1),
    Facing.DOWN: (0, 1),
    Facing.LEFT: (-1, 0),
    Facing.RIGHT: (1, 0)
}

WEAPON_SCORES = {
    "axe": 10,
    "sword": 40,
    "knife": 10,
    "amulet": 30,
    "bow_unloaded": 40,
    "bow_loaded": 40
}

MAP_SIZE = 200


class BB8Strategy(ABC):
    def __init__(self):
        self.ACTIONS_WITH_WEIGHTS = {
            characters.Action.TURN_LEFT: 0.2,
            characters.Action.TURN_RIGHT: 0.2,
            characters.Action.STEP_FORWARD: 0.5,
            characters.Action.ATTACK: 0.1,
        }

        self.first_name = None
        self.position = None
        self.enemy_nearby = False
        self.visible_tiles = {}
        self.weapon = "axe"
        self.weapon_range = 1
        self.facing = None
        self.map = np.zeros((MAP_SIZE, MAP_SIZE))
        self.weapon_positions = {}
        self.menhir_position = None
        self.visited_passages = []
        self.going_to_passage = False
        self.destination = None

    @abstractmethod
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        pass

    def behave_randomly(self):
        return random.choices(population=list(self.ACTIONS_WITH_WEIGHTS.keys()),
                              weights=list(self.ACTIONS_WITH_WEIGHTS.values()),
                              k=1)[0]

    def study_map(self):
        self.map[self.position.x, self.position.y] = 1
        for position, description in self.visible_tiles.items():
            if description.type == "land":
                self.map[position[0], position[1]] = 1

            elif description.type == "menhir":
                self.map[position[0], position[1]] = 1
                self.menhir_position = coordinates.Coords(position[0], position[1])

            if description.loot is not None:
                self.weapon_positions[position] = description.loot.name

    def find_best_weapon(self):
        best_score = 0
        best_coordinates = None

        for (weapon_position, weapon_name) in self.weapon_positions.items():
            weapon_coordinates = coordinates.Coords(weapon_position[0], weapon_position[1])
            distance = self.calculate_distance(weapon_coordinates) + 1  # to avoid 0 division
            weapon_score = WEAPON_SCORES[weapon_name]
            real_score = weapon_score if weapon_score > WEAPON_SCORES[self.weapon] else 0

            score = 0.5 * real_score / (0.3 * distance)

            if score > best_score:
                best_score = score
                best_coordinates = weapon_coordinates
                if self.weapon == weapon_name:
                    best_coordinates = None

        return best_coordinates if best_score > 0 else None

    def calculate_distance(self, other_position: coordinates.Coords) -> int:
        distance = math.sqrt((self.position.x - other_position.x) ** 2 + (self.position.y - other_position.y) ** 2)
        return int(round(distance))

    def get_enemy_in_range_coordinates(self):
        visible_enemies = {k: v for k, v in self.visible_tiles.items() if
                           v.character is not None and v.character.controller_name != self.first_name}

        for enemy_position in visible_enemies.keys():
            enemy_coordinates = coordinates.Coords(enemy_position[0], enemy_position[1])
            if self.calculate_distance(enemy_coordinates) <= self.weapon_range:
                return enemy_coordinates

        return None

    def is_mist_coming(self):
        mist_tiles = {k: v for k, v in self.visible_tiles.items() if v.effects}
        return True if mist_tiles else False

    def get_desired_facing(self, destination_coordinates: coordinates.Coords):
        r_vect = coordinates.Coords(destination_coordinates.x - self.position.x,
                                    destination_coordinates.y - self.position.y)
        angle = math.atan2(r_vect.y, r_vect.x)

        if PI / 4.0 < angle <= 3.0 * PI / 4.0:
            desired_facing = Facing.UP
        elif -1.0 * PI / 4.0 < angle <= PI / 4.0:
            desired_facing = Facing.RIGHT
        elif -3.0 * PI / 4.0 < angle <= -1.0 * PI / 4.0:
            desired_facing = Facing.DOWN
        else:
            desired_facing = Facing.LEFT

        return desired_facing

    def rotate_to_desired_facing(self, desired_facing):
        return ROTATIONS[(self.facing, desired_facing)]

    def go_to_direction(self, destination_coordinates: coordinates.Coords):
        grid = Grid(matrix=self.map)
        start = grid.node(self.position.x, self.position.y)
        end = grid.node(destination_coordinates.x, destination_coordinates.y)
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        path, runs = finder.find_path(start, end, grid)

        if path:
            next_step = path[0]
            desired_facing = self.get_desired_facing(coordinates.Coords(next_step[0], next_step[1]))
            if self.facing == desired_facing:
                return characters.Action.STEP_FORWARD
            else:
                return self.rotate_to_desired_facing(desired_facing)
        else:
            return self.go_forward()

    def go_forward(self):
        next_step_x = min(self.position.x + FACING_COORDS[self.facing][0], MAP_SIZE)
        next_step_y = min(self.position.y + FACING_COORDS[self.facing][1], MAP_SIZE)

        random_factor = random.random()
        if random_factor <= 0.33:
            return characters.Action.TURN_RIGHT

        if self.map[next_step_x, next_step_y] != 0:
            return characters.Action.STEP_FORWARD
        else:
            return characters.Action.TURN_LEFT

    def parse_knowledge(self, knowledge: characters.ChampionKnowledge):
        self.position = knowledge.position
        self.visible_tiles = knowledge.visible_tiles
        self.first_name = self.visible_tiles[self.position].character.controller_name
        self.facing = self.visible_tiles[self.position].character.facing

    def find_passage(self):
        best_passage_coords = None
        min_distance = 10000

        for i in range(MAP_SIZE):
            blocked_count = 0
            pass_count = 0
            for j in range(MAP_SIZE):
                if self.map[i, j] == 0:
                    blocked_count += 1
                    if pass_count == 1:
                        pass_count = 0
                        passage_coords = coordinates.Coords(i, j)
                        if self.calculate_distance(passage_coords) < min_distance and passage_coords not in self.visited_passages:
                            best_passage_coords = passage_coords
                            min_distance = self.calculate_distance(best_passage_coords)
                else:
                    pass_count += 1
        for i in range(MAP_SIZE):
            blocked_count = 0
            pass_count = 0
            for j in range(MAP_SIZE):
                if self.map[j, i] == 0:
                    blocked_count += 1
                    if pass_count == 1:
                        pass_count = 0
                        passage_coords = coordinates.Coords(i, j)
                        if self.calculate_distance(passage_coords) < min_distance and passage_coords not in self.visited_passages:
                            best_passage_coords = passage_coords
                            min_distance = self.calculate_distance(best_passage_coords)
                else:
                    pass_count += 1

        return best_passage_coords

    def explore(self):
        best_passage_coords = self.find_passage()
        if best_passage_coords is not None:
            self.destination = best_passage_coords
            self.visited_passages.append(best_passage_coords)
            return self.go_to_direction(best_passage_coords)

        return self.go_forward()

    def go_to_destination_if_exists(self):
        if self.destination is not None:
            if self.position == self.destination:
                self.destination = None
            else:
                return self.go_to_direction(self.destination)
        return None


class RandomStrategy(BB8Strategy):
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.behave_randomly()


class EscapeToMenhirStrategy(BB8Strategy):
    def __init__(self):
        super().__init__()
        self.is_at_menhir = False

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.parse_knowledge(knowledge)
        self.study_map()

        go_to_destination_action = self.go_to_destination_if_exists()
        if go_to_destination_action is not None:
            return go_to_destination_action

        if not self.is_at_menhir:
            if self.menhir_position is not None:
                if self.calculate_distance(self.menhir_position) == 1:
                    self.is_at_menhir = True
                self.destination = self.menhir_position
                return self.go_to_direction(self.menhir_position)
            else:
                return self.go_forward()
        else:
            enemy_in_range_coordinates = self.get_enemy_in_range_coordinates()
            if enemy_in_range_coordinates is not None:
                desired_facing = self.get_desired_facing(enemy_in_range_coordinates)
                if desired_facing == self.facing:
                    return characters.Action.ATTACK
                else:
                    return self.rotate_to_desired_facing(enemy_in_range_coordinates)

        return self.behave_randomly()


class FindBestWeaponStrategy(BB8Strategy):
    def __init__(self):
        super().__init__()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.parse_knowledge(knowledge)
        self.study_map()

        go_to_destination_action = self.go_to_destination_if_exists()
        if go_to_destination_action is not None:
            return go_to_destination_action

        if self.is_mist_coming() and self.menhir_position is not None:
            self.destination = self.menhir_position
            return self.go_to_direction(self.menhir_position)
        elif self.is_mist_coming():
            self.go_forward()

        best_weapon_coordinates = self.find_best_weapon()
        enemy_in_range_coordinates = self.get_enemy_in_range_coordinates()

        if best_weapon_coordinates is not None:
            self.destination = best_weapon_coordinates
            return self.go_to_direction(best_weapon_coordinates)

        if enemy_in_range_coordinates is not None:
            desired_facing = self.get_desired_facing(enemy_in_range_coordinates)
            if desired_facing == self.facing:
                return characters.Action.ATTACK
            else:
                return self.rotate_to_desired_facing(enemy_in_range_coordinates)

        return self.behave_randomly()
    
class RLStrategy(BB8Strategy):
    def __init__(self):
        super().__init__()
        self.round_health = None
        self.q_learning_state = None
        self.sight_range = 2000
        self.long_seq = 6
        
    def update_bot(self, knowledge: characters.ChampionKnowledge):
        self.bot_position = knowledge.position
        character         = knowledge.visible_tiles[self.bot_position].character
        self.weapon       = character.weapon.name
        self.facing       = character.facing
        self.last_round_health = self.round_health
        self.round_health = character.health
        
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.update_bot(knowledge)
            return self.choose_next_step(knowledge)
        except Exception as e:
            return self.behave_randomly()
        
    def has_next_defined(self):
        return len(self.queue) > 0
    
    def choose_next_step(self, knowledge: characters.ChampionKnowledge) -> None:
        # Choose action based on Q learning
        self.find_vector_to_nearest_mist_tile(knowledge)
        state = calculate_state(self.last_observed_mist_vec)
        (state, action) = learn_actions(state)
        if self.last_round_health is not None and self.q_learning_state is not None:
            # q-values update
            (old_state, old_action) = self.q_learning_state
            reward = 0
            if self.last_round_health == self.round_health:
                reward += 0.5
            else:
                reward += -50
            if old_action == QAction.RUN_AWAY:
                reward+=-1
            update_q_values(old_state, old_action, reward, state)

        self.q_learning_state = (state, action)

        # Perform chosen action
        if action == QAction.RUN_AWAY:
            return self.go_to_direction(self.menhir_position) 
        elif action == QAction.IGNORE:
            return characters.Action.DO_NOTHING

    def find_vector_to_nearest_mist_tile(self, knowledge: characters.ChampionKnowledge):
        g_distance = lambda my_p, ref_p: ((ref_p[0] - my_p[0]) ** 2 + (ref_p[1] - my_p[1]) ** 2)
        g_distance_vec = lambda vec: ((vec[0]) ** 2 + (vec[1]) ** 2)
        
        mist_tiles: dict[coordinates.Coords, int] = defaultdict(int) #dict for storing distance to each mist tile from current bot position
        visible_tiles = knowledge.visible_tiles

        for coord in visible_tiles.keys():
            if g_distance(self.bot_position, coord) <= self.sight_range:
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
                if self.run_seq_step == self.long_seq:
                    self.run_seq_step = 1

        return self.last_observed_mist_vec
  