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
    '=': TileDescription(type='sea', loot=None, character=None, effects=[]),
    '.': TileDescription(type='land', loot=None, character=None, effects=[]),
    '#': TileDescription(type='wall', loot=None, character=None, effects=[]),
}

WEAPON_ENCODING = {
    'K': WeaponDescription(name='knife'),
    'S': WeaponDescription(name='sword'),
    'A': WeaponDescription(name='axe'),
    'B': WeaponDescription(name='bow_unloaded'),
    'M': WeaponDescription(name='amulet'),
}

INFINITY: int = 99999999
TURNS_TO_FOG: int = 150
MENHIR: Coords = Coords(9, 9)


class Strategy(enum.Enum):
    SPIN = 'spin'
    ATTACK = 'attack'
    MOVE_TO_CENTER = 'move_to_center'
    ESCAPE = 'escape'
    RANDOM = 'random'
    MINIMIZE_RISK = 'minimize_risk'
    ANTI_IDLE = 'anti_idle'
    CHANGE_CLUSTER = 'change_cluster'


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
        self.load_arena()
        self.create_clusters()

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
            self.tiles[Coords(tile[0], tile[1])] = knowledge.visible_tiles[tile]
            if tile == self.position:
                self.facing = knowledge.visible_tiles[tile].character.facing
                self.weapon = knowledge.visible_tiles[tile].character.weapon
                if self.health > knowledge.visible_tiles[tile].character.health:
                    self.run = 5
                    self.health = knowledge.visible_tiles[tile].character.health
            elif knowledge.visible_tiles[tile].character is not None:
                self.known_enemies[knowledge.visible_tiles[tile].character.controller_name] \
                    = (Coords(tile[0], tile[1]), knowledge.visible_tiles[tile].character, -1)
                for cluster in self.clusters:
                    if Coords(tile[0], tile[1]) in cluster.tiles:
                        cluster.extra_danger[knowledge.visible_tiles[tile].character.controller_name] = 1.0
                    else:
                        cluster.extra_danger[knowledge.visible_tiles[tile].character.controller_name] = 0.0
            if knowledge.visible_tiles[tile].type == 'menhir' and self.menhir is None:
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
                                                                  self.known_enemies[enemy][1].facing)[1]
                    + value[2] + 1)
            self.danger_ratings['left'] = \
                min(self.danger_ratings['left'], self.find_path(self.known_enemies[enemy][0],
                                                                self.forward(self.position, Facing.LEFT),
                                                                self.known_enemies[enemy][1].facing)[1]
                    + value[2] + 1)
            self.danger_ratings['right'] = \
                min(self.danger_ratings['right'], self.find_path(self.known_enemies[enemy][0],
                                                                 self.forward(self.position, Facing.RIGHT),
                                                                 self.known_enemies[enemy][1].facing)[1]
                    + value[2] + 1)
            self.danger_ratings['up'] = \
                min(self.danger_ratings['up'], self.find_path(self.known_enemies[enemy][0],
                                                              self.forward(self.position, Facing.UP),
                                                              self.known_enemies[enemy][1].facing)[1]
                    + value[2] + 1)
            self.danger_ratings['down'] = \
                min(self.danger_ratings['down'], self.find_path(self.known_enemies[enemy][0],
                                                                self.forward(self.position, Facing.DOWN),
                                                                self.known_enemies[enemy][1].facing)[1])

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
        elif not all(enemy[2] >= 2 or not self.is_in_range(enemy[0]) for enemy in self.known_enemies.values()):
            strategy = Strategy.ATTACK
        elif self.run > 0 and self.tiles[self.forward(self.position, self.facing)].type in ('land', 'menhir'):
            strategy = Strategy.ESCAPE
        elif self.spinning_stage < 4:
            strategy = Strategy.SPIN
        elif random.random() * TURNS_TO_FOG * 2 < self.turn and self.menhir is not None:
            strategy = Strategy.MOVE_TO_CENTER
        elif (self.clusters[self.current_cluster].danger_sum > 9.0 and min([self.clusters[x].danger_sum for x in self.clusters[self.current_cluster].neighbors]) < 9.0) or (random.random() * TURNS_TO_FOG < self.turn and self.menhir is None):
            strategy = Strategy.CHANGE_CLUSTER
        elif random.random() * 100 < best_rating:
            strategy = Strategy.RANDOM
        else:
            strategy = Strategy.MINIMIZE_RISK

        # Update some values
        if self.run > 0:
            self.run -= 1
        if self.spinning_stage < 4 and strategy == Strategy.SPIN:
            self.spinning_stage += 1
            if self.spinning_stage == 4 and self.current_cluster in self.explored_clusters:
                self.explored_clusters.append(self.current_cluster)

        # Execute strategy
        if strategy == Strategy.ANTI_IDLE:
            self.idle_time = 0
            return characters.Action.TURN_LEFT
        if strategy == Strategy.ATTACK:
            return characters.Action.ATTACK
        elif strategy == Strategy.ESCAPE:
            return characters.Action.STEP_FORWARD
        elif strategy == Strategy.SPIN:
            return characters.Action.TURN_LEFT
        elif strategy == Strategy.MOVE_TO_CENTER:
            if self.menhir is not None:
                self.path = self.find_path(self.position, self.menhir, self.facing)[0]
                return self.get_action_to_move_in_path()
            else:
                neighbors = []
                for neighbor in self.clusters[self.current_cluster].neighbors:
                    neighbors.append(neighbor)
                while neighbors and len(neighbors) > 0:
                    least_danger = INFINITY
                    best_neighbor = neighbors[0]
                    for neighbor in neighbors:
                        if neighbor in self.clusters and least_danger > self.clusters[neighbor].danger_sum:
                            best_neighbor = neighbors
                            least_danger = self.clusters[neighbor].danger_sum + (100.0 if self.menhir is None and neighbor not in self.explored_clusters else 0.0)
                    if best_neighbor in neighbors:
                        neighbors.remove(best_neighbor)
                    path_to_center = self.find_path(self.position, self.clusters[best_neighbor].central_point, self.facing)
                    path_to_center = path_to_center[0] if path_to_center else path_to_center
                    enemy_in_sight = False
                    if self.path is not None and len(self.path) > 0:
                        for enemy in self.known_enemies.values():
                            if enemy[2] == 0 and np.sqrt(np.power(enemy[0].x - self.path[0].x, 2) + np.power(enemy[0].y - self.path[0].y, 2)) < 5.0:
                                enemy_in_sight = True
                    else:
                        enemy_in_sight = True

                    if not enemy_in_sight:
                        return self.get_action_to_move_in_path()

                return self.pick_action(best_move)
        elif strategy == Strategy.CHANGE_CLUSTER:
            neighbors = []
            for neighbor in self.clusters[self.current_cluster].neighbors:
                neighbors.append(neighbor)
            while neighbors and len(neighbors) > 0:
                least_danger = INFINITY
                best_neighbor = neighbors[0]
                for neighbor in neighbors:
                    if neighbor in self.clusters and least_danger > self.clusters[neighbor].danger_sum:
                        best_neighbor = neighbors
                        least_danger = self.clusters[neighbor].danger_sum + (100.0 if self.menhir is None and neighbor not in self.explored_clusters else 0.0)
                if best_neighbor in neighbors:
                    neighbors.remove(best_neighbor)
                path_to_center = self.find_path(self.position, self.clusters[best_neighbor].central_point, self.facing)
                path_to_center = path_to_center[0] if path_to_center else path_to_center
                enemy_in_sight = False
                if self.path is not None and len(self.path) > 0:
                    for enemy in self.known_enemies.values():
                        if enemy[2] == 0 and np.sqrt(np.power(enemy[0].x - self.path[0].x, 2) + np.power(enemy[0].y - self.path[0].y, 2)) < 5.0:
                            enemy_in_sight = True
                else:
                    enemy_in_sight = True

                if not enemy_in_sight:
                    return self.get_action_to_move_in_path()

            return self.pick_action(best_move)
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
        self.load_arena()
        self.create_clusters()

    @property
    def name(self) -> str:
        return f'DodgeController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.STRIPPED

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
                current_coords = coords_per_no_neighbors[i][0]
                new_cluster.tiles[current_coords] = self.tiles[current_coords]
                to_be_checked = []
                to_be_found = []
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if not (dx == 0 and dy == 0):
                            is_found = False
                            for neighbor_list in coords_per_no_neighbors.values():
                                if Coords(current_coords.x + dx, current_coords.y + dy) in neighbor_list:
                                    is_found = True
                                    break
                            if is_found:
                                to_be_found.append(Coords(current_coords.x + dx, current_coords.y + dy))

                to_be_found.append(current_coords)

                for neighbor_list in coords_per_no_neighbors.values():
                    for neighbor in to_be_found:
                        if neighbor in neighbor_list:
                            neighbor_list.remove(neighbor)
                            if neighbor in to_be_found:
                                to_be_found.remove(neighbor)
                            to_be_checked.append(neighbor)

                while len(to_be_checked) > 0:
                    currently_checked = to_be_checked.pop()
                    new_cluster.tiles[currently_checked] = self.tiles[currently_checked]
                    neighbor_indices = []
                    mini_neighbor_indices = []
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if not (dx == 0 and dy == 0):
                                to_be_found.append(Coords(currently_checked.x + dx, currently_checked.y + dy))
                                for cluster in self.clusters:
                                    if Coords(currently_checked.x + dx, currently_checked.y + dy) in cluster.tiles.keys():
                                        neighbor_indices.append(cluster.index)
                                for mini_cluster in mini_clusters:
                                    if Coords(currently_checked.x + dx, currently_checked.y + dy) in mini_cluster.tiles.keys():
                                        mini_neighbor_indices.append(mini_cluster.index)

                    for index in neighbor_indices:
                        if index not in new_cluster.neighbors:
                            new_cluster.neighbors.append(index)
                    for index in mini_neighbor_indices:
                        if index not in new_cluster.mini_neighbors:
                            new_cluster.mini_neighbors.append(index)

                    while len(to_be_found) > 0:
                        next_neighbor = to_be_found.pop()
                        count_in_cluster = 0
                        for dx in [-1, 0, 1]:
                            for dy in [-1, 0, 1]:
                                if not (dx == 0 and dy == 0):
                                    if new_cluster.tiles.get(Coords(currently_checked.x + dx, currently_checked.y + dy)) is not None:
                                        count_in_cluster += 1

                        if count_in_cluster >= 3:
                            for neighbor_list in coords_per_no_neighbors.values():
                                if next_neighbor in neighbor_list:
                                    neighbor_list.remove(next_neighbor)
                                    to_be_checked.append(next_neighbor)

                if len(new_cluster.tiles.keys()) > 9:
                    new_cluster.index = len(self.clusters)
                    self.clusters.append(new_cluster)
                else:
                    new_cluster.index = len(mini_clusters)
                    mini_clusters.append(new_cluster)

        for cluster in self.clusters:
            for neighbor in cluster.neighbors:
                if cluster.index not in self.clusters[neighbor].neighbors:
                    self.clusters[neighbor].neighbors.append(cluster.index)
            for neighbor in cluster.mini_neighbors:
                if cluster.index not in mini_clusters[neighbor].neighbors:
                    mini_clusters[neighbor].neighbors.append(cluster.index)
        for cluster in mini_clusters:
            for neighbor in cluster.neighbors:
                if cluster.index not in self.clusters[neighbor].mini_neighbors:
                    self.clusters[neighbor].mini_neighbors.append(cluster.index)
            for neighbor in cluster.mini_neighbors:
                if cluster.index not in mini_clusters[neighbor].mini_neighbors:
                    mini_clusters[neighbor].mini_neighbors.append(cluster.index)

        # Step 3
        remaining_mini_clusters = [x for x in range(len(mini_clusters))]
        to_be_moved_up = []
        for size in range(1, 10):
            for mini_cluster in mini_clusters:
                if len(mini_cluster.tiles.keys()) == size and mini_cluster.index in remaining_mini_clusters:
                    remaining_mini_clusters.remove(mini_cluster.index)
                    optimal_neighbor = None
                    optimal_neighbor_size = -1
                    for mini_neighbor_index in mini_cluster.mini_neighbors:
                        mini_neighbor = mini_clusters[mini_neighbor_index]
                        if 10 > len(mini_neighbor.tiles.keys()) > optimal_neighbor_size or optimal_neighbor_size < 0:
                            optimal_neighbor = mini_neighbor_index
                            optimal_neighbor_size = len(mini_neighbor.tiles.keys())
                    if optimal_neighbor is None:
                        for neighbor_index in mini_cluster.neighbors:
                            neighbor = mini_clusters[neighbor_index]
                            if len(neighbor.tiles.keys()) > optimal_neighbor_size:
                                optimal_neighbor = neighbor_index
                                optimal_neighbor_size = len(neighbor.tiles.keys())

                    if optimal_neighbor is not None:
                        for tile in mini_cluster.tiles.keys():
                            mini_clusters[optimal_neighbor].tiles[tile] = mini_cluster.tiles[tile]
                        for neighbor in mini_cluster.neighbors:
                            if neighbor not in mini_clusters[optimal_neighbor].neighbors:
                                mini_clusters[optimal_neighbor].neighbors.append(neighbor)
                        for mini_neighbor in mini_cluster.mini_neighbors:
                            if mini_neighbor not in mini_clusters[optimal_neighbor].mini_neighbors:
                                mini_clusters[optimal_neighbor].mini_neighbors.append(mini_neighbor)

                        if len(mini_clusters[optimal_neighbor].tiles) > 9:
                            to_be_moved_up.append(optimal_neighbor)
                            if optimal_neighbor in remaining_mini_clusters:
                                remaining_mini_clusters.remove(optimal_neighbor)

        for cluster_index in to_be_moved_up:
            self.clusters.append(mini_clusters[cluster_index])
            mini_clusters[cluster_index].index = len(self.clusters) - 1
            for i in range(len(self.clusters) - 1):
                if cluster_index in self.clusters[i].mini_neighbors:
                    self.clusters[i].neighbors.append(mini_clusters[cluster_index].index)

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
                        elif character in WEAPON_ENCODING:
                            self.tiles[position] = TileDescription(type=TILE_ENCODING['.'].type,
                                                                   loot=WEAPON_ENCODING[character],
                                                                   character=None,
                                                                   effects=[])

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

    def find_path(self, start: Coords, end: Coords, facing: Facing) -> (Optional[List[Coords]], int):
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

                return trace, int(current.h_cost + current.g_cost)

            neighbors: [Coords] = [add_coords(current.coords, (Coords(0, 1))),
                                   add_coords(current.coords, (Coords(0, -1))),
                                   add_coords(current.coords, (Coords(1, 0))),
                                   add_coords(current.coords, (Coords(-1, 0)))]

            for neighbor in neighbors:
                if neighbor in self.tiles.keys() and (self.tiles[neighbor].type == 'land' or self.tiles[
                    neighbor].type == 'menhir') and neighbor not in closed_coords.keys():
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

        trace: Optional[List[Coords]] = None
        return trace, INFINITY


POTENTIAL_CONTROLLERS = [
    DodgeController("ElvisNaProchach")
]
