import os
import random
import enum
from typing import NamedTuple, Optional, List, Tuple

import numpy as np

from gupb import controller
from gupb.controller.elvis.cluster import Cluster
from gupb.model import arenas
from gupb.model import characters
from gupb.model.coordinates import Coords, add_coords, sub_coords
from gupb.model.tiles import TileDescription
from gupb.model.characters import Facing, Action, ChampionDescription, PENALISED_IDLE_TIME
from gupb.model.weapons import WeaponDescription

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

TILE_ENCODING = {
    '=': TileDescription(type='sea', loot=None, character=None, effects=[], consumable=None),
    '.': TileDescription(type='land', loot=None, character=None, effects=[], consumable=None),
    '#': TileDescription(type='wall', loot=None, character=None, effects=[], consumable=None),
}

WEAPON_ENCODING = {
    'K': WeaponDescription(name='knife'),
    'S': WeaponDescription(name='sword'),
    'A': WeaponDescription(name='axe'),
    'B': WeaponDescription(name='bow_unloaded'),
    'M': WeaponDescription(name='amulet'),
}

INFINITY: int = 99999999
TURNS_TO_FOG: int = 120
EXPLORATION_MULTIPLIER = 0.8
BANDIT = False
EPSILON = 0.1


class Strategy(enum.Enum):
    SPIN = 'spin'
    ATTACK = 'attack'
    MOVE_TO_CENTER = 'move_to_center'
    ESCAPE = 'escape'
    RANDOM = 'random'
    MINIMIZE_RISK = 'minimize_risk'
    ANTI_IDLE = 'anti_idle'
    CHANGE_CLUSTER = 'change_cluster'
    MOVE_TO_CENTER_OF_CLUSTER = 'move_to_center_of_cluster'
    MOVE_TO_POTION = 'move_to_potion'
    COMBAT = 'combat'
    GO_TO_WEAPON = 'go_to_weapon'


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class DodgeController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.tiles: {Coords: TileDescription} = {}
        self.spinning_stage = 0
        self.position: Coords = Coords(-1, -1)
        self.facing: Facing = Facing.UP
        self.path: Optional[List[Coords]] = None
        self.target: Optional[Coords] = None
        self.weapon: WeaponDescription = WeaponDescription(name='knife')
        self.known_enemies: {str: Tuple[Coords, ChampionDescription, int]} = {}
        self.danger_ratings: {str: int} = {'left': INFINITY,
                                           'right': INFINITY,
                                           'down': INFINITY,
                                           'up': INFINITY,
                                           'center': INFINITY}
        self.turn: int = 0
        self.health: int = 8
        self.run: int = 0
        self.idle_time = 0
        self.last_position = None
        self.last_facing = None
        self.arena_name = 'generated_0' if os.path.exists('resources/arenas/generated_0.gupb') else 'island'
        self.menhir: Optional[Coords] = None
        self.clusters: List[Cluster] = []
        self.explored_clusters: List[int] = []
        self.current_cluster: int = -1
        self.number_of_enemies = 13
        self.unexplored = Cluster(0)
        self.round = 0
        self.grand_strategy = {}
        self.grand_strategy_counters = {}
        self.current_grand_strategy = 5
        self.exploration_multiplier = EXPLORATION_MULTIPLIER
        self.consumable_coords = None
        self.dangerous_tiles: List[Coords] = []
        self.misty_tiles: List[Coords] = []
        self.future_dangerous_tiles: List[Coords] = []
        self.current_enemy: Optional[str] = None
        self.good_weapon_in_sight: Optional[Coords] = None
        self.current_enemy_expiration: int = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DodgeController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # Gather information from seen tiles
        self.turn += 1
        self.last_facing = self.facing
        self.last_position = self.position
        self.position = knowledge.position
        self.number_of_enemies = knowledge.no_of_champions_alive
        self.dangerous_tiles = list(set(self.misty_tiles[:] + self.future_dangerous_tiles[:]))
        self.future_dangerous_tiles = []
        if self.current_enemy_expiration > 0:
            self.current_enemy = None
        self.current_enemy_expiration = 0 if self.current_enemy_expiration == 0 else self.current_enemy_expiration - 1
        self.good_weapon_in_sight = None

        if self.consumable_coords is not None and knowledge.visible_tiles.get((self.consumable_coords.x, self.consumable_coords.y)) is not None and knowledge.visible_tiles[(self.consumable_coords.x, self.consumable_coords.y)].consumable is None:
            self.consumable_coords = None

        for i in range(len(self.clusters)):
            if self.position in self.clusters[i].tiles.keys():
                self.current_cluster = i

        danger_changes = [{} for cluster in self.clusters]
        for i in range(len(self.clusters)):
            cluster = self.clusters[i]
            for neighbor in cluster.neighbors:
                distance = cluster.get_distance_between_centers_of_mass(self.clusters[neighbor].center_of_mass)
                if distance == 0.0:
                    if i in self.clusters[neighbor].neighbors:
                        self.clusters[neighbor].neighbors.remove(i)
                    if neighbor in cluster.neighbors:
                        cluster.neighbors.remove(neighbor)
                    continue
                percentage_lost = 0.25 / distance
                for danger in cluster.extra_danger.keys():
                    if danger_changes[i].get(danger) is None:
                        danger_changes[i][danger] = -percentage_lost * cluster.extra_danger[danger]
                    else:
                        danger_changes[i][danger] -= percentage_lost * cluster.extra_danger[danger]
                    if danger_changes[neighbor].get(danger) is None:
                        danger_changes[neighbor][danger] = percentage_lost * cluster.extra_danger[danger]
                    else:
                        danger_changes[neighbor][danger] += percentage_lost * cluster.extra_danger[danger]
        for i in range(len(danger_changes)):
            for danger in danger_changes[i].keys():
                if self.clusters[i].extra_danger.get(danger) is None:
                    self.clusters[i].extra_danger[danger] = danger_changes[i][danger]
                else:
                    self.clusters[i].extra_danger[danger] += danger_changes[i][danger]

        for tile in knowledge.visible_tiles:
            if knowledge.visible_tiles[tile].effects is not None and knowledge.visible_tiles[tile].effects != []:
                if Coords(tile[0], tile[1]) not in self.misty_tiles:
                    self.misty_tiles.append(Coords(tile[0], tile[1]))
                if Coords(tile[0], tile[1]) not in self.dangerous_tiles:
                    self.dangerous_tiles.append(Coords(tile[0], tile[1]))

            if knowledge.visible_tiles[tile].consumable is not None:
                self.consumable_coords = Coords(tile[0], tile[1])

            if knowledge.visible_tiles[tile].loot is not None:
                if knowledge.visible_tiles[tile].loot.name in ('axe', 'sword'):
                    self.good_weapon_in_sight = Coords(tile[0], tile[1])

            self.tiles[Coords(tile[0], tile[1])] = knowledge.visible_tiles[tile]
            if (Coords(tile[0], tile[1])) in self.unexplored.tiles.keys():
                self.unexplored.tiles.pop(Coords(tile[0], tile[1]))
            if tile == self.position:
                self.facing = knowledge.visible_tiles[tile].character.facing
                self.weapon = knowledge.visible_tiles[tile].character.weapon
                if self.health > knowledge.visible_tiles[tile].character.health:
                    self.run = 5
                    self.health = knowledge.visible_tiles[tile].character.health
            elif knowledge.visible_tiles[tile].character is not None:
                self.known_enemies[knowledge.visible_tiles[tile].character.controller_name] \
                    = (Coords(tile[0], tile[1]), knowledge.visible_tiles[tile].character, -1)
                dangerous_tiles = self.tiles_in_range(Coords(tile[0], tile[1]), knowledge.visible_tiles[tile].character.facing, knowledge.visible_tiles[tile].character.weapon)

                if knowledge.visible_tiles[tile].character.health <= self.health - 4 and self.find_path(self.position, Coords(tile[0], tile[1]), self.facing)[1] < 5 and self.weapon.name in ('axe', 'sword'):
                    self.current_enemy = knowledge.visible_tiles[tile].character.controller_name
                    self.current_enemy_expiration = 2

                if Coords(tile[0], tile[1]) not in dangerous_tiles:
                    dangerous_tiles.append(Coords(tile[0], tile[1]))
                self.dangerous_tiles = list(set(self.dangerous_tiles + dangerous_tiles))

                future_dangerous_tiles = dangerous_tiles[:]
                future_dangerous_tiles += self.tiles_in_range(Coords(tile[0], tile[1]),
                                                              knowledge.visible_tiles[tile].character.facing.turn_left(),
                                                              'bow_loaded' if knowledge.visible_tiles[tile].character.weapon == 'bow_unloaded' else knowledge.visible_tiles[tile].character.weapon)
                future_dangerous_tiles += self.tiles_in_range(Coords(tile[0], tile[1]),
                                                              knowledge.visible_tiles[tile].character.facing.turn_right(),
                                                              'bow_loaded' if knowledge.visible_tiles[tile].character.weapon == 'bow_unloaded' else knowledge.visible_tiles[tile].character.weapon)

                if self.tiles[self.forward(Coords(tile[0], tile[1]), knowledge.visible_tiles[tile].character.facing)].type in ('land', 'menhir'):
                    future_dangerous_tiles += self.tiles_in_range(self.forward(Coords(tile[0], tile[1]), knowledge.visible_tiles[tile].character.facing),
                                                                  knowledge.visible_tiles[tile].character.facing,
                                                                  'bow_loaded' if knowledge.visible_tiles[tile].character.weapon == 'bow_unloaded' else knowledge.visible_tiles[tile].character.weapon)

                self.future_dangerous_tiles = list(set(future_dangerous_tiles + self.future_dangerous_tiles))
                for cluster in self.clusters:
                    if Coords(tile[0], tile[1]) in cluster.tiles:
                        cluster.extra_danger[knowledge.visible_tiles[tile].character.controller_name] = 1.0
                    else:
                        cluster.extra_danger[knowledge.visible_tiles[tile].character.controller_name] = 0.0
            if knowledge.visible_tiles[tile].type == 'menhir':
                if knowledge.visible_tiles[tile].character is not None and self.position != Coords(tile[0], tile[1]) and TURNS_TO_FOG * 1.3 < self.turn:
                    self.current_enemy = knowledge.visible_tiles[tile].character.controller_name
                    self.current_enemy_expiration = 2
                if self.menhir is None:
                    self.menhir = Coords(tile[0], tile[1])
                    for cluster in self.clusters:
                        if Coords(tile[0], tile[1]) in cluster.tiles:
                            cluster.contains_menhir = True
                            cluster.set_base_danger(self.number_of_enemies)
                            break

        for cluster in self.clusters:
            cluster.update_danger(self.number_of_enemies)

        if self.position == self.clusters[self.current_cluster].central_point and self.current_cluster not in self.explored_clusters and self.spinning_stage == 4:
            self.spinning_stage = 0

        if self.position == self.last_position and self.facing == self.last_facing:
            self.idle_time += 1
        else:
            self.idle_time = 0

        # Update risks
        for enemy in self.known_enemies.keys():
            value = self.known_enemies[enemy]
            self.known_enemies[enemy] = value[0], value[1], value[2] + 1
            self.danger_ratings['center'] = \
                min(self.danger_ratings['center'], self.find_path(self.known_enemies[enemy][0],
                                                                  self.position,
                                                                  self.known_enemies[enemy][1].facing,
                                                                  True,
                                                                  True)[1]
                    + value[2] + 1)
            self.danger_ratings['left'] = \
                min(self.danger_ratings['left'], self.find_path(self.known_enemies[enemy][0],
                                                                self.forward(self.position, Facing.LEFT),
                                                                self.known_enemies[enemy][1].facing,
                                                                True,
                                                                True)[1]
                    + value[2] + 1)
            self.danger_ratings['right'] = \
                min(self.danger_ratings['right'], self.find_path(self.known_enemies[enemy][0],
                                                                 self.forward(self.position, Facing.RIGHT),
                                                                 self.known_enemies[enemy][1].facing,
                                                                 True,
                                                                 True)[1]
                    + value[2] + 1)
            self.danger_ratings['up'] = \
                min(self.danger_ratings['up'], self.find_path(self.known_enemies[enemy][0],
                                                              self.forward(self.position, Facing.UP),
                                                              self.known_enemies[enemy][1].facing,
                                                              True,
                                                              True)[1]
                    + value[2] + 1)
            self.danger_ratings['down'] = \
                min(self.danger_ratings['down'], self.find_path(self.known_enemies[enemy][0],
                                                                self.forward(self.position, Facing.DOWN),
                                                                self.known_enemies[enemy][1].facing,
                                                                True,
                                                                True)[1])

        # Find the safest move
        best_move: str = 'center'
        best_rating: int = -1
        for move in ('left', 'right', 'up', 'down', 'center'):
            if self.danger_ratings[move] > best_rating and self.move_possible(move):
                best_rating = self.danger_ratings[move]
                best_move = move

        # Choose strategy for the turn
        strategy: Strategy = Strategy.RANDOM
        if self.idle_time == PENALISED_IDLE_TIME - 1:
            strategy = Strategy.ANTI_IDLE
        elif not all(enemy[2] >= 2 or not self.is_in_range(enemy[0]) for enemy in self.known_enemies.values()) and (self.current_enemy is None or self.known_enemies[self.current_enemy][1].health <= 2):
            strategy = Strategy.ATTACK
        elif self.current_enemy is not None:
            strategy = Strategy.COMBAT
        elif self.run > 0 and not ((self.menhir is not None and TURNS_TO_FOG * 1.3 < self.turn) or (self.menhir is None and TURNS_TO_FOG * self.exploration_multiplier < self.turn)):
            strategy = Strategy.ESCAPE
        elif self.spinning_stage < 4:
            strategy = Strategy.SPIN
        elif self.current_grand_strategy > 2 and (self.menhir is not None and TURNS_TO_FOG * 1.3 < self.turn) or (self.menhir is None and TURNS_TO_FOG * self.exploration_multiplier < self.turn):
            strategy = Strategy.MOVE_TO_CENTER
        elif self.consumable_coords is not None:
            strategy = Strategy.MOVE_TO_POTION
        elif self.good_weapon_in_sight is not None and self.good_weapon_in_sight not in self.dangerous_tiles and self.good_weapon_in_sight not in self.future_dangerous_tiles and self.weapon.name not in ('axe', 'sword') and self.find_path(self.position, self.good_weapon_in_sight, self.facing, True, True)[1] < 10 and self.position != self.good_weapon_in_sight:
            strategy = Strategy.GO_TO_WEAPON
        elif self.current_grand_strategy % 2 == 1 and len(self.clusters[self.current_cluster].neighbors) > 0 and (min([self.clusters[x].danger_sum for x in self.clusters[self.current_cluster].neighbors]) < (self.clusters[self.current_cluster].danger_sum - 0.5)):
            strategy = Strategy.CHANGE_CLUSTER
        elif self.current_grand_strategy % 2 == 1 and self.current_cluster not in self.explored_clusters:
            strategy = Strategy.MOVE_TO_CENTER_OF_CLUSTER
        elif random.random() * 100 < best_rating:
            strategy = Strategy.RANDOM
        else:
            strategy = Strategy.MINIMIZE_RISK

        # Update some values
        if self.run > 0:
            self.run -= 1
        if self.spinning_stage < 4 and strategy == Strategy.SPIN:
            self.spinning_stage += 1
            if self.spinning_stage == 4 and self.current_cluster not in self.explored_clusters:
                self.explored_clusters.append(self.current_cluster)

        # Execute strategy
        if strategy == Strategy.ANTI_IDLE:
            self.idle_time = 0
            return characters.Action.TURN_LEFT
        if strategy == Strategy.ATTACK:
            return characters.Action.ATTACK
        elif strategy == Strategy.COMBAT:
            enemy_position = self.known_enemies[self.current_enemy][0]
            attack_points = self.get_potential_attack_points(enemy_position, self.weapon)

            own_distances = self.find_paths(self.position, enemy_position, attack_points, self.facing, False, self.weapon.name not in ('axe', 'sword'))

            self.target = attack_points[own_distances.index(min(own_distances))]

            if self.target == self.position:
                if self.is_in_range(self.known_enemies[self.current_enemy][0]):
                    return characters.Action.ATTACK
                else:
                    self.path = self.find_path(self.position, enemy_position, self.facing)[0][1:]
                    return self.get_action_to_move_in_path()

            self.path = self.find_path(self.position, self.target, self.facing)[0][1:]

            return self.get_action_to_move_in_path()
        elif strategy == Strategy.ESCAPE:
            if self.tiles[self.forward(self.position, self.facing)].type in ('land', 'menhir') \
                    and self.forward(self.position, self.facing) not in self.dangerous_tiles:
                return characters.Action.STEP_FORWARD
            elif self.tiles[self.forward(self.position, self.facing.turn_right())].type in ('land', 'menhir') \
                    and self.forward(self.position, self.facing.turn_right()) not in self.dangerous_tiles:
                return characters.Action.TURN_RIGHT
            elif self.tiles[self.forward(self.position, self.facing.turn_left())].type in ('land', 'menhir') \
                    and self.forward(self.position, self.facing.turn_left()) not in self.dangerous_tiles:
                return characters.Action.TURN_LEFT
            elif self.tiles[self.forward(self.position, self.facing.turn_left().turn_left())].type in ('land', 'menhir') \
                    and self.forward(self.position, self.facing.turn_left().turn_left()) not in self.dangerous_tiles:
                return characters.Action.TURN_LEFT
            elif self.tiles[self.forward(self.position, self.facing)].type in ('land', 'menhir'):
                return characters.Action.STEP_FORWARD
            elif self.tiles[self.forward(self.position, self.facing.turn_right())].type in ('land', 'menhir'):
                return characters.Action.TURN_RIGHT
            else:
                return characters.Action.TURN_LEFT
        elif strategy == Strategy.SPIN:
            return characters.Action.TURN_LEFT
        elif strategy == Strategy.MOVE_TO_CENTER:
            if self.menhir is not None:
                if self.position == self.menhir:
                    return characters.Action.TURN_LEFT
                else:
                    self.target = self.menhir
                    self.path = self.find_path(self.position, self.menhir, self.facing)[0][1:]
                    return self.get_action_to_move_in_path()
            else:
                self.unexplored.find_central_point()
                self.path = self.find_path(self.position, self.unexplored.central_point, self.facing)[0][1:]
                return self.get_action_to_move_in_path()
        elif strategy == Strategy.MOVE_TO_POTION:
            self.path = self.find_path(self.position, self.consumable_coords, self.facing)[0][1:]
            return self.get_action_to_move_in_path()
        elif strategy == Strategy.GO_TO_WEAPON:
            self.path = self.find_path(self.position, self.good_weapon_in_sight, self.facing)[0][1:]
            return self.get_action_to_move_in_path()
        elif strategy == Strategy.CHANGE_CLUSTER:
            neighbors = []
            for neighbor in self.clusters[self.current_cluster].neighbors:
                neighbors.append(neighbor)
            while len(neighbors) > 0:
                least_danger = INFINITY
                best_neighbor = neighbors[0]
                for neighbor in neighbors:
                    if neighbor in [x.index for x in self.clusters] and least_danger > self.clusters[neighbor].danger_sum:
                        best_neighbor = neighbor
                        least_danger = self.clusters[neighbor].danger_sum
                if best_neighbor in neighbors:
                    neighbors.remove(best_neighbor)
                self.path = self.find_path(self.position, self.clusters[best_neighbor].central_point, self.facing)[0][1:]
                enemy_in_sight = False
                if self.path is not None and len(self.path) > 0:
                    for enemy in self.known_enemies.values():
                        if enemy[2] < 5 and np.sqrt(np.power(enemy[0].x - self.path[0].x, 2) + np.power(enemy[0].y - self.path[0].y, 2)) < 3.0:
                            enemy_in_sight = True
                else:
                    enemy_in_sight = True

                if not enemy_in_sight:
                    return self.get_action_to_move_in_path()

            return self.pick_action(best_move)
        elif strategy == Strategy.MOVE_TO_CENTER_OF_CLUSTER:
            self.path = self.find_path(self.position, self.clusters[self.current_cluster].central_point, self.facing)[0][1:]
            enemy_in_sight = False
            if self.path is not None and len(self.path) > 0:
                for enemy in self.known_enemies.values():
                    if enemy[2] < 5 and np.sqrt(np.power(enemy[0].x - self.path[0].x, 2) + np.power(enemy[0].y - self.path[0].y, 2)) < 3.0:
                        enemy_in_sight = True
            else:
                enemy_in_sight = True

            if enemy_in_sight:
                return self.pick_action(best_move)
            else:
                return self.get_action_to_move_in_path()
        elif strategy == Strategy.RANDOM:
            return random.choice(POSSIBLE_ACTIONS)
        else:
            return self.pick_action(best_move)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.tiles: {Coords: TileDescription} = {}
        self.spinning_stage = 0
        self.position: Coords = Coords(-1, -1)
        self.facing: Facing = Facing.UP
        self.path: Optional[List[Coords]] = None
        self.target: Optional[Coords] = None
        self.weapon: WeaponDescription = WeaponDescription(name='knife')
        self.known_enemies: {str: Tuple[Coords, ChampionDescription, int]} = {}
        self.danger_ratings: {str: int} = {'left': INFINITY,
                                           'right': INFINITY,
                                           'down': INFINITY,
                                           'up': INFINITY,
                                           'center': INFINITY}
        self.turn: int = 0
        self.round += 1
        self.current_grand_strategy = self.select_grand_strategy(arena_description.name)
        self.exploration_multiplier = 0.6 if self.current_grand_strategy < 4 else (0.7 if self.current_grand_strategy < 6 else 1.0)
        self.health: int = 8
        self.run: int = 0
        self.idle_time = 0
        self.last_position = None
        self.last_facing = None
        self.arena_name = arena_description.name
        self.menhir: Optional[Coords] = None
        self.clusters: List[Cluster] = []
        self.explored_clusters: List[int] = []
        self.current_cluster: int = -1
        self.number_of_enemies = 13
        self.unexplored = Cluster(0)
        self.load_arena()
        self.create_clusters()
        self.consumable_coords = None
        self.dangerous_tiles = []
        self.misty_tiles = []
        self.future_dangerous_tiles = []
        self.current_enemy = None
        self.good_weapon_in_sight = None
        self.current_enemy_expiration = 0

    @property
    def name(self) -> str:
        return f'DodgeController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.STRIPPED

    def select_grand_strategy(self, name: str):
        if not BANDIT:
            return 5

        place = self.number_of_enemies
        if place == 2 and self.health < 2:
            place = 1

        last_reward = 1
        reward = 1
        for i in range(13, place - 1, -1):
            reward = reward + last_reward
            last_reward = reward - last_reward

        if self.round > 1:
            self.grand_strategy_counters[self.arena_name][self.current_grand_strategy] += 1
            self.grand_strategy[self.arena_name][self.current_grand_strategy] += (1 / self.grand_strategy_counters[self.arena_name][self.current_grand_strategy]) * (reward - self.grand_strategy[self.arena_name][self.current_grand_strategy])

        if name not in self.grand_strategy.keys():
            self.grand_strategy[name] = [0.0] * 8
            self.grand_strategy_counters[name] = [0] * 8

        if random.random() < EPSILON or self.round < 300:
            return int(random.random() * 8)
        else:
            number_of_good_strategies = len(list(filter(lambda x: x == max(self.grand_strategy[name]), self.grand_strategy[name])))
            chosen_strategy = int(random.random() * number_of_good_strategies)
            for strategy, value in enumerate(self.grand_strategy[name]):
                if value == max(self.grand_strategy[name]):
                    if chosen_strategy == 0:
                        return strategy
                    else:
                        chosen_strategy -= 1

    def get_action_to_move_in_path(self) -> characters.Action:
        direction = sub_coords(self.path[0], self.position)
        if direction == self.facing.value:
            self.path.pop(0)
            return characters.Action.STEP_FORWARD
        elif direction == self.facing.turn_left().value:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT

    def create_clusters(self):
        # Step 1
        coords_per_no_neighbors = {0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: [], 7: [], 8: []}
        for coords in self.tiles.keys():
            if self.tiles[coords].type not in ('land', 'menhir'):
                continue

            count = 0
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if not (dx == 0 and dy == 0) and self.tiles.get(Coords(coords.x + dx, coords.y + dy)) is not None and self.tiles.get(Coords(coords.x + dx, coords.y + dy)).type in ('land', 'menhir'):
                        count += 1

            coords_per_no_neighbors[count].append(coords)

        # Step 2
        mini_clusters = []
        for i in range(8, -1, -1):
            while len(coords_per_no_neighbors[i]) > 0:
                new_cluster = Cluster(len(self.clusters))
                to_check = []
                current_coords = coords_per_no_neighbors[i].pop()
                to_check.append(current_coords)
                new_cluster.tiles[current_coords] = self.tiles[current_coords]
                for (dx, dy) in [(1, 0), (0, 1), (-1, 0), (0, -1)]:
                    current_neighbor = Coords(current_coords.x + dx, current_coords.y + dy)
                    is_available = True
                    cluster_index = -1
                    mini_cluster_index = -1
                    if self.tiles[current_neighbor].type in ('land', 'menhir'):
                        for cluster in self.clusters:
                            if current_neighbor in cluster.tiles.keys():
                                is_available = False
                                cluster_index = cluster.index
                                break
                        if is_available:
                            for mini_cluster in mini_clusters:
                                if current_neighbor in mini_cluster.tiles.keys():
                                    is_available = False
                                    mini_cluster_index = mini_cluster.index
                                    break

                        if is_available:
                            to_check.append(current_neighbor)
                            new_cluster.tiles[current_neighbor] = self.tiles[current_neighbor]
                        else:
                            if cluster_index >= 0:
                                if cluster_index not in new_cluster.neighbors:
                                    new_cluster.neighbors.append(cluster_index)
                            elif mini_cluster_index >= 0:
                                if mini_cluster_index not in new_cluster.mini_neighbors:
                                    new_cluster.mini_neighbors.append(mini_cluster_index)

                while len(to_check) > 0:
                    current_coords = to_check.pop()
                    for neighbor_list in coords_per_no_neighbors.values():
                        if current_coords in neighbor_list:
                            neighbor_list.remove(current_coords)

                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            current_neighbor = Coords(current_coords.x + dx, current_coords.y + dy)
                            if self.tiles[current_neighbor].type in ('land', 'menhir') and current_neighbor not in new_cluster.tiles.keys():
                                is_available = True
                                cluster_index = -1
                                mini_cluster_index = -1
                                for cluster in self.clusters:
                                    if current_neighbor in cluster.tiles.keys():
                                        is_available = False
                                        cluster_index = cluster.index
                                        break
                                if is_available:
                                    for mini_cluster in mini_clusters:
                                        if current_neighbor in mini_cluster.tiles.keys():
                                            is_available = False
                                            mini_cluster_index = mini_cluster.index
                                            break

                                if is_available:
                                    neighbor_count = 0
                                    passable_count = 0
                                    for dx2 in [-1, 0, 1]:
                                        for dy2 in [-1, 0, 1]:
                                            current_neighbors_neighbor = Coords(current_neighbor.x + dx2, current_neighbor.y + dy2)
                                            if self.tiles[current_neighbors_neighbor].type in ('land', 'menhir'):
                                                passable_count += 1
                                            if not (dx2 == 0 and dy2 == 0) and current_neighbors_neighbor in new_cluster.tiles.keys():
                                                neighbor_count += 1

                                    if neighbor_count >= 3:
                                        to_check.append(current_neighbor)
                                        new_cluster.tiles[current_neighbor] = self.tiles[current_neighbor]
                                    else:
                                        if current_neighbor not in coords_per_no_neighbors[passable_count - neighbor_count]:
                                            for neighbor_list in coords_per_no_neighbors.values():
                                                if current_neighbor in neighbor_list:
                                                    neighbor_list.remove(current_neighbor)
                                                    coords_per_no_neighbors[passable_count - neighbor_count].append(current_neighbor)
                                                    break
                                else:
                                    if (dx, dy) in [(-1, 0), (1, 0), (0, 1), (0, -1)]:
                                        if cluster_index >= 0:
                                            if cluster_index not in new_cluster.neighbors:
                                                new_cluster.neighbors.append(cluster_index)
                                        elif mini_cluster_index >= 0:
                                            if mini_cluster_index not in new_cluster.mini_neighbors:
                                                new_cluster.mini_neighbors.append(mini_cluster_index)

                if len(new_cluster.tiles.keys()) >= 9:
                    self.clusters.append(new_cluster)
                    for neighbor in new_cluster.neighbors:
                        if new_cluster.index not in self.clusters[neighbor].neighbors:
                            self.clusters[neighbor].neighbors.append(new_cluster.index)
                    for mini_neighbor in new_cluster.mini_neighbors:
                        if new_cluster.index not in mini_clusters[mini_neighbor].neighbors:
                            mini_clusters[mini_neighbor].neighbors.append(new_cluster.index)
                else:
                    new_cluster.index = len(mini_clusters)
                    mini_clusters.append(new_cluster)
                    for neighbor in new_cluster.neighbors:
                        if new_cluster.index not in self.clusters[neighbor].mini_neighbors:
                            self.clusters[neighbor].mini_neighbors.append(new_cluster.index)
                    for mini_neighbor in new_cluster.mini_neighbors:
                        if new_cluster.index not in mini_clusters[mini_neighbor].mini_neighbors:
                            mini_clusters[mini_neighbor].mini_neighbors.append(new_cluster.index)

        # Step 3
        remaining_mini_clusters = [x for x in range(len(mini_clusters))]
        to_be_moved_up = []
        for size in range(1, 10):
            for mini_cluster in mini_clusters:
                if len(mini_cluster.tiles.keys()) == size and mini_cluster.index in remaining_mini_clusters:
                    remaining_mini_clusters.remove(mini_cluster.index)
                    optimal_neighbor = None
                    optimal_neighbor_size = -1
                    is_mini_neighbor = True
                    for mini_neighbor_index in mini_cluster.mini_neighbors:
                        mini_neighbor = mini_clusters[mini_neighbor_index]
                        if 10 > len(mini_neighbor.tiles.keys()) > max(optimal_neighbor_size, 0) or (optimal_neighbor_size < 0 and len(mini_neighbor.tiles.keys()) > 0) or (optimal_neighbor_size > 9 and 10 > len(mini_neighbor.tiles.keys()) > 0):
                            optimal_neighbor = mini_neighbor
                            optimal_neighbor_size = len(mini_neighbor.tiles.keys())
                    if optimal_neighbor is None:
                        for neighbor_index in mini_cluster.neighbors:
                            neighbor = self.clusters[neighbor_index]
                            if len(neighbor.tiles.keys()) > optimal_neighbor_size:
                                is_mini_neighbor = False
                                optimal_neighbor = neighbor
                                optimal_neighbor_size = len(neighbor.tiles.keys())

                    if optimal_neighbor is not None:
                        for tile in mini_cluster.tiles.keys():
                            optimal_neighbor.tiles[tile] = mini_cluster.tiles[tile]
                        mini_cluster.tiles.clear()
                        for neighbor in mini_cluster.neighbors:
                            if neighbor not in optimal_neighbor.neighbors:
                                optimal_neighbor.neighbors.append(neighbor)
                                if is_mini_neighbor:
                                    self.clusters[neighbor].mini_neighbors.append(optimal_neighbor.index)
                                else:
                                    self.clusters[neighbor].neighbors.append(optimal_neighbor.index)
                        for mini_neighbor in mini_cluster.mini_neighbors:
                            if mini_neighbor not in optimal_neighbor.mini_neighbors:
                                optimal_neighbor.mini_neighbors.append(mini_neighbor)
                                if is_mini_neighbor:
                                    mini_clusters[mini_neighbor].mini_neighbors.append(optimal_neighbor.index)
                                else:
                                    mini_clusters[mini_neighbor].neighbors.append(optimal_neighbor.index)

                        for cluster in self.clusters:
                            if cluster.index in cluster.neighbors:
                                cluster.neighbors.remove(cluster.index)
                            if mini_cluster.index in cluster.mini_neighbors:
                                cluster.mini_neighbors.remove(mini_cluster.index)
                        for other_mini_cluster in mini_clusters:
                            if other_mini_cluster.index in other_mini_cluster.mini_neighbors:
                                other_mini_cluster.mini_neighbors.remove(other_mini_cluster.index)
                            if mini_cluster.index in other_mini_cluster.mini_neighbors:
                                other_mini_cluster.mini_neighbors.remove(mini_cluster.index)

                        if optimal_neighbor not in self.clusters and len(optimal_neighbor.tiles.keys()) > 9:
                            if optimal_neighbor.index not in to_be_moved_up:
                                to_be_moved_up.append(optimal_neighbor.index)
                            if optimal_neighbor in remaining_mini_clusters:
                                remaining_mini_clusters.remove(optimal_neighbor.index)

        for cluster_index in to_be_moved_up:
            mini_clusters[cluster_index].index = len(self.clusters)
            self.clusters.append(mini_clusters[cluster_index])
            for i in range(len(self.clusters) - 1):
                if cluster_index in self.clusters[i].mini_neighbors:
                    self.clusters[i].neighbors.append(mini_clusters[cluster_index].index)
                    self.clusters[i].mini_neighbors.remove(cluster_index)

        # Step 4
        for cluster in self.clusters:
            cluster.find_central_point()

        # Step 5
        for cluster in self.clusters:
            for neighbor in cluster.neighbors:
                cluster.neighbor_distances.append(cluster.get_distance_between_centers_of_mass(self.clusters[neighbor].center_of_mass))

        # Step 6
        for cluster in self.clusters:
            cluster.set_base_danger(self.number_of_enemies)

    def load_arena(self):
        with open(os.path.abspath('resources/arenas/' + self.arena_name + '.gupb')) as file:
            for y, line in enumerate(file.readlines()):
                for x, character in enumerate(line):
                    if character != '\n':
                        position = Coords(x, y)
                        if character in TILE_ENCODING:
                            self.tiles[position] = TILE_ENCODING[character]
                            if self.tiles[position].type in ('menhir', 'land'):
                                self.unexplored.tiles[position] = self.tiles[position]
                        elif character in WEAPON_ENCODING:
                            self.tiles[position] = TileDescription(type=TILE_ENCODING['.'].type,
                                                                   loot=WEAPON_ENCODING[character],
                                                                   character=None,
                                                                   effects=[],
                                                                   consumable=None)
                            if self.tiles[position].type in ('menhir', 'land'):
                                self.unexplored.tiles[position] = self.tiles[position]

    def move_possible(self, move):
        if move == 'center':
            return True
        if move == 'left':
            return self.tiles[self.forward(self.position, Facing.LEFT)].type in ('land', 'menhir')
        if move == 'right':
            return self.tiles[self.forward(self.position, Facing.RIGHT)].type in ('land', 'menhir')
        if move == 'up':
            return self.tiles[self.forward(self.position, Facing.UP)].type in ('land', 'menhir')
        if move == 'right':
            return self.tiles[self.forward(self.position, Facing.RIGHT)].type in ('land', 'menhir')

    def pick_action(self, direction: str) -> Action:
        if direction == 'center':
            return characters.Action.TURN_LEFT

        correct_facing: Facing
        if direction == 'left':
            correct_facing = Facing.LEFT
        elif direction == 'right':
            correct_facing = Facing.RIGHT
        elif direction == 'up':
            correct_facing = Facing.UP
        else:
            correct_facing = Facing.DOWN

        if correct_facing.value == self.facing.value:
            return characters.Action.STEP_FORWARD

        if correct_facing.turn_left().value == self.facing.value:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_LEFT

    def forward(self, current_coords: Coords, direction: Facing) -> Coords:
        if direction == Facing.LEFT:
            return Coords(current_coords.x - 1, current_coords.y)
        if direction == Facing.RIGHT:
            return Coords(current_coords.x + 1, current_coords.y)
        if direction == Facing.UP:
            return Coords(current_coords.x, current_coords.y - 1)
        if direction == Facing.DOWN:
            return Coords(current_coords.x, current_coords.y + 1)


    def tiles_in_range(self, position: Coords, facing: Facing, weapon: WeaponDescription) -> List[Coords]:
        if weapon.name == 'knife':
            return [add_coords(position, facing.value)]
        if weapon.name == 'sword':
            return [add_coords(position, facing.value),
                               Coords(position.x + 2 * facing.value.x, position.y + 2 * facing.value.y),
                               Coords(position.x + 3 * facing.value.x, position.y + 3 * facing.value.y)]
        if weapon.name == 'axe':
            return [add_coords(position, facing.value),
                               Coords(position.x - facing.value.y, position.y - facing.value.x),
                               Coords(position.x + facing.value.y, position.y + facing.value.x)]
        if weapon.name == 'bow_loaded':
            return_coords = []
            current_position = Coords(position.x + 1, position.y)
            while current_position in self.tiles.keys():
                return_coords.append(current_position)
                current_position = Coords(current_position.x + 1, current_position.y)
            current_position = Coords(position.x - 1, position.y)
            while current_position in self.tiles.keys():
                return_coords.append(current_position)
                current_position = Coords(current_position.x - 1, current_position.y)
            current_position = Coords(position.x, position.y + 1)
            while current_position in self.tiles.keys():
                return_coords.append(current_position)
                current_position = Coords(current_position.x, current_position.y + 1)
            current_position = Coords(position.x, position.y - 1)
            while current_position in self.tiles.keys():
                return_coords.append(current_position)
                current_position = Coords(current_position.x, current_position.y - 1)
            return return_coords
        if weapon.name == 'amulet':
            return [Coords(position.x + 1, position.y + 1),
                           Coords(position.x - 1, position.y - 1),
                           Coords(position.x + 1, position.y - 1),
                           Coords(position.x - 1, position.y + 1),
                           Coords(position.x - 2, position.y + 2),
                           Coords(position.x - 2, position.y - 2),
                           Coords(position.x + 2, position.y - 2),
                           Coords(position.x + 2, position.y + 2)]
        return []
    def is_in_range(self, enemy_coords: Coords) -> bool:
        if self.weapon.name == 'knife':
            return enemy_coords in [add_coords(self.position, self.facing.value)]
        if self.weapon.name == 'sword':
            return enemy_coords in [add_coords(self.position, self.facing.value),
                                    Coords(self.position.x + 2 * self.facing.value.x,
                                           self.position.y + 2 * self.facing.value.y),
                                    Coords(self.position.x + 3 * self.facing.value.x,
                                           self.position.y + 3 * self.facing.value.y)]
        if self.weapon.name == 'axe':
            return enemy_coords in [add_coords(self.position, self.facing.value),
                                    Coords(self.position.x - self.facing.value.y,
                                           self.position.y - self.facing.value.x),
                                    Coords(self.position.x + self.facing.value.y,
                                           self.position.y + self.facing.value.x)]
        if self.weapon.name == 'bow_unloaded' or self.weapon.name == 'bow_loaded':
            diff_vector: Coords = sub_coords(enemy_coords, self.position)
            if diff_vector.x * diff_vector.y != 0:
                return False
            if diff_vector.x * self.facing.value.x + diff_vector.y * self.facing.value.y <= 0:
                return False
            return True
        if self.weapon.name == 'amulet':
            return enemy_coords in [Coords(self.position.x + 1, self.position.y + 1),
                                    Coords(self.position.x - 1, self.position.y - 1),
                                    Coords(self.position.x + 1, self.position.y - 1),
                                    Coords(self.position.x - 1, self.position.y + 1),
                                    Coords(self.position.x - 2, self.position.y + 2),
                                    Coords(self.position.x - 2, self.position.y - 2),
                                    Coords(self.position.x + 2, self.position.y - 2),
                                    Coords(self.position.x + 2, self.position.y + 2)]
        return False

    def get_facing(self, f_coords: Coords) -> Facing:
        if f_coords == Coords(0, 1):
            return Facing.DOWN
        elif f_coords == Coords(0, -1):
            return Facing.UP
        elif f_coords == Coords(1, 0):
            return Facing.LEFT
        elif f_coords == Coords(-1, 0):
            return Facing.RIGHT

    def find_path(self, start: Coords, end: Coords, facing: Facing, dangerous=False, risky=False) -> (Optional[List[Coords]], int):
        def get_h_cost(h_start: Coords, h_end: Coords, h_facing: Facing) -> int:
            distance: int = abs(h_end.y - h_start.y) + abs(h_end.x - h_start.x)
            direction: Coords = Coords(1 if h_end.x - h_start.x > 0 else -1 if h_end.x - h_start.x < 0 else 0,
                                       1 if h_end.y - h_start.y > 0 else -1 if h_end.y - h_start.y < 0 else 0)
            turns = abs(h_facing.value.x - direction.x) + abs(h_facing.value.y - direction.y)
            return (turns if turns <= 2 else 2) + distance

        a_coords = NamedTuple('a_coords', [('coords', Coords),
                                           ('g_cost', int),
                                           ('h_cost', int),
                                           ('parent', Optional[Coords]),
                                           ('facing', Facing)])

        open_coords: [a_coords] = []
        closed_coords: {Coords: a_coords} = {}
        open_coords.append(a_coords(start, 0, get_h_cost(start, end, facing), None, facing))

        risky_path = None if risky else self.find_path(start, end, facing, dangerous, True)

        while len(open_coords) > 0:

            open_coords = list(sorted(open_coords, key=lambda x: (x.g_cost + x.h_cost, x.h_cost), reverse=False))
            current: a_coords = open_coords.pop(0)
            closed_coords[current.coords] = current

            if current.coords == end:
                trace: Optional[List[Coords]] = [current.coords]
                current_parent: Optional[a_coords] = current

                while current_parent.parent is not None:
                    current_parent = closed_coords[current_parent.parent]
                    trace.insert(0, current_parent.coords)

                if not risky:
                    if int(current.h_cost + current.g_cost) > risky_path[1] + 10:
                        return risky_path

                return trace, int(current.h_cost + current.g_cost)

            neighbors: [Coords] = [add_coords(current.coords, (Coords(0, 1))),
                                   add_coords(current.coords, (Coords(0, -1))),
                                   add_coords(current.coords, (Coords(1, 0))),
                                   add_coords(current.coords, (Coords(-1, 0)))]

            for neighbor in neighbors:
                if neighbor in self.tiles.keys()\
                        and (self.tiles[neighbor].type == 'land' or self.tiles[neighbor].type == 'menhir')\
                        and neighbor not in closed_coords.keys()\
                        and (dangerous or neighbor not in self.dangerous_tiles)\
                        and (risky or neighbor not in self.future_dangerous_tiles):
                    neighbor_direction: Coords = Coords(neighbor.x - current.coords.x, neighbor.y - current.coords.y)
                    neighbor_g_cost = (1 if neighbor_direction == current.facing.value else
                                       3 if add_coords(neighbor_direction, current.facing.value) == Coords(0, 0) else 2) \
                                      + current.g_cost
                    neighbor_h_cost = get_h_cost(neighbor, end, self.get_facing(neighbor_direction))

                    for coords in open_coords:
                        if coords.coords == neighbor:
                            open_coords.remove(coords)

                    open_coords.append(a_coords(neighbor,
                                                neighbor_g_cost,
                                                neighbor_h_cost,
                                                current.coords,
                                                self.get_facing(neighbor_direction)))
        if not risky:
            return risky_path
        if not dangerous:
            return self.find_path(start, end, facing, True, True)
        trace: Optional[List[Coords]] = None
        return trace, INFINITY

    def find_paths(self, start: Coords, end: Coords, targets: List[Coords], facing: Facing, dangerous=False, risky=False) -> List[int]:
        def get_h_cost(h_start: Coords, h_end: Coords, h_facing: Facing) -> int:
            distance: int = abs(h_end.y - h_start.y) + abs(h_end.x - h_start.x)
            direction: Coords = Coords(1 if h_end.x - h_start.x > 0 else -1 if h_end.x - h_start.x < 0 else 0,
                                       1 if h_end.y - h_start.y > 0 else -1 if h_end.y - h_start.y < 0 else 0)
            turns = abs(h_facing.value.x - direction.x) + abs(h_facing.value.y - direction.y)
            return (turns if turns <= 2 else 2) + distance

        a_coords = NamedTuple('a_coords', [('coords', Coords),
                                           ('g_cost', int),
                                           ('h_cost', int),
                                           ('parent', Optional[Coords]),
                                           ('facing', Facing)])

        open_coords: [a_coords] = []
        closed_coords: {Coords: a_coords} = {}
        open_coords.append(a_coords(start, 0, get_h_cost(start, end, facing), None, facing))

        targets_g_cost: List[int] = [-INFINITY] * len(targets)
        while len(open_coords) > 0:

            open_coords = list(sorted(open_coords, key=lambda x: (x.g_cost + x.h_cost, x.h_cost), reverse=False))
            current: a_coords = open_coords.pop(0)
            closed_coords[current.coords] = current

            if current.coords in targets:
                targets_g_cost[targets.index(current.coords)] = current.g_cost + current.h_cost

            if sum(targets_g_cost) > 0:
                return targets_g_cost

            neighbors: [Coords] = [add_coords(current.coords, (Coords(0, 1))),
                                   add_coords(current.coords, (Coords(0, -1))),
                                   add_coords(current.coords, (Coords(1, 0))),
                                   add_coords(current.coords, (Coords(-1, 0)))]

            for neighbor in neighbors:
                if neighbor in self.tiles.keys()\
                        and (self.tiles[neighbor].type == 'land' or self.tiles[neighbor].type == 'menhir')\
                        and neighbor not in closed_coords.keys()\
                        and (dangerous or neighbor not in self.dangerous_tiles)\
                        and (risky or neighbor not in self.future_dangerous_tiles):
                    neighbor_direction: Coords = Coords(neighbor.x - current.coords.x, neighbor.y - current.coords.y)
                    neighbor_g_cost = (1 if neighbor_direction == current.facing.value else
                                       3 if add_coords(neighbor_direction, current.facing.value) == Coords(0, 0) else 2) \
                                      + current.g_cost
                    neighbor_h_cost = get_h_cost(neighbor, end, self.get_facing(neighbor_direction))

                    for coords in open_coords:
                        if coords.coords == neighbor:
                            open_coords.remove(coords)

                    open_coords.append(a_coords(neighbor,
                                                neighbor_g_cost,
                                                neighbor_h_cost,
                                                current.coords,
                                                self.get_facing(neighbor_direction)))
        if not risky:
            return self.find_paths(start, end, targets, facing, dangerous, True)
        if not dangerous:
            return self.find_paths(start, end, targets, facing, True, True)
        return targets_g_cost

    def get_potential_attack_points(self, enemy_point: Coords, own_weapon: WeaponDescription, dangerous=False, risky=False) -> List[Coords]:
        points: List[Coords] = []
        facings = [Facing.UP, Facing.DOWN, Facing.RIGHT, Facing.LEFT]
        for facing in facings:
            points += self.tiles_in_range(enemy_point, facing, own_weapon if own_weapon.name != 'bow_unloaded' else WeaponDescription('bow_loaded'))
        points = list(set(points))

        points = list(filter(lambda x: x in self.tiles.keys() and self.tiles[x].type in ('land', 'menhir'), points))
        if not risky:
            filtered = list(filter(lambda x: x not in self.future_dangerous_tiles, points))
            if len(filtered) == 0:
                return points
            points = filtered
        if not dangerous:
            filtered = list(filter(lambda x: x not in self.dangerous_tiles, points))
            if len(filtered) == 0:
                return points
            points = filtered

        return points


POTENTIAL_CONTROLLERS = [
    DodgeController("ElvisNaProchach")
]
