import random
from collections import deque
from math import atan2
from typing import List, Dict

from gupb import controller
from gupb.controller.random import POSSIBLE_ACTIONS
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import Facing, CHAMPION_STARTING_HP
from gupb.model.coordinates import Coords
from gupb.model.profiling import profile
import json


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class WIETnamczyk(controller.Controller):
    GET_WEAPON = "get_weapon"
    EXPLORE = "explore"
    PANIC = "panic"
    GO_TO_MENHIR = "go_to_menhir"
    SURROUND_MENHIR = "surrond_menhir"
    MIST_PANIC_MODE = False
    EPSILON = 0.1

    def __init__(self):
        self.mist_range = 3
        self.enemy_range = 5
        self.strategies_dict = {'OSTRICH': self.strategy_ostrich, 'BERSERKER': self.strategy_berserker,
                                'COWARD': self.strategy_coward}
        # These values were obtained using K-armed bandit approach :)
        self.Q = {'BERSERKER': 7.138888888888888,
                  'COWARD': 10.453237410071942,
                  'OSTRICH': 10.596923076923078}
        self.N = {'OSTRICH': 0, 'BERSERKER': 0, 'COWARD': 0}
        self.strategies = list(self.Q.keys())

        rand = random.uniform(0, 1)
        self.current_strategy = random.choice(self.strategies) if rand < WIETnamczyk.EPSILON else max(self.Q,
                                                                                                      key=self.Q.get)

        self.menhir_pos = None
        self.good_weapons = ["sword", "axe", "bow_unloaded", "bow_loaded"]
        self.first_name: str = "Adam"
        self.arena_description = None
        self.current_weapon = "knife"
        self.state = WIETnamczyk.GET_WEAPON
        self.next_dest = None
        self.hp = CHAMPION_STARTING_HP
        self.prev_hp = CHAMPION_STARTING_HP
        self.facing = None
        self.exploration_goal = None
        self.action_queue = []

    def dist(self, tile1: coordinates.Coords, tile2: coordinates.Coords):
        if not tile1 or not tile2:
            return 0
        dist = abs(tile1[0] - tile2[0]) + abs(tile1[1] - tile2[1])
        return dist

    def max_dist(self, tile1: coordinates.Coords, tile2: coordinates.Coords):
        return max(abs(tile1[0] - tile2[0]), abs(tile1[1] - tile2[1]))

    def bfs_dist(self, tile1: coordinates.Coords, tile2: coordinates.Coords):
        return len(self.find_path(tile1, tile2))

    def get_random_safe_place(self, current_pos: coordinates.Coords):
        places = list(sorted(map(lambda place: (place, self.dist(place, current_pos)), self.safe_places),
                             key=lambda pair: pair[1]))
        return random.choices(places, weights=self.prob)[0][0]

    def should_fight(self, self_pos: coordinates.Coords, enemy_pos: coordinates.Coords,
                     enemy_tile: tiles.TileDescription) -> bool:
        enemy_hp = enemy_tile.character.health
        enemy_weapon = enemy_tile.character.weapon
        enemy_facing = enemy_tile.character.facing
        weapon_reach = {'sword': 3, 'axe': 1, 'knife': 1}
        if self.current_weapon.name not in ['bow_loaded', 'bow_unloaded', 'amulet']:
            bfs_distance = self.bfs_dist(self_pos, enemy_pos)
            max_dist = weapon_reach[self.current_weapon.name] + 1
            if self.hp - enemy_hp >= 3 and bfs_distance <= max_dist:
                return True
        return False

    def should_attack(self, self_pos: coordinates.Coords, knowledge: characters.ChampionKnowledge):
        if self.current_weapon.name == 'sword':
            for tile, description in knowledge.visible_tiles.items():
                distance = self.dist(tile, self_pos)
                if distance == 0 or (description.character is None or distance > 3):
                    continue
                if (self.facing == Facing.UP or self.facing == Facing.DOWN) and (tile[0] - self_pos[0]) == 0:
                    return True
                if (self.facing == Facing.LEFT or self.facing == Facing.RIGHT) and (tile[1] - self_pos[1]) == 0:
                    return True
        if self.current_weapon.name == 'axe':
            for tile, description in knowledge.visible_tiles.items():
                if self.max_dist(tile, self_pos) != 1:
                    continue
                if description.character is not None:
                    return True
        if self.current_weapon.name == 'amulet':
            for tile, description in knowledge.visible_tiles.items():
                if self.max_dist(tile, self_pos) > 1:
                    continue
                if description.character is not None and self.dist(tile, self_pos) == 2:
                    return True
        if 'bow' in self.current_weapon.name:
            for tile, description in knowledge.visible_tiles.items():
                distance = self.dist(tile, self_pos)
                if distance == 0 or description.character is None:
                    continue
                if (self.facing == Facing.UP or self.facing == Facing.DOWN) and (tile[0] - self_pos[0]) == 0:
                    return True
                if (self.facing == Facing.LEFT or self.facing == Facing.RIGHT) and (tile[1] - self_pos[1]) == 0:
                    return True
        if self.current_weapon.name == 'knife':
            for tile, description in knowledge.visible_tiles.items():
                distance = self.dist(tile, self_pos)
                if description.character is None or distance != 1:
                    continue
                if (self.facing == Facing.UP or self.facing == Facing.DOWN) and (tile[0] - self_pos[0]) == 0:
                    return True
                if (self.facing == Facing.LEFT or self.facing == Facing.RIGHT) and (tile[1] - self_pos[1]) == 0:
                    return True
        return False

    def find_good_weapon(self, bot_pos):
        weapons_pos = []
        for i in range(len(self.map)):
            for j in range(len(self.map[0])):
                weapon_opt = self.map[i][j].loot
                if weapon_opt and weapon_opt.name in self.good_weapons:
                    weapons_pos.append((i, j))
        # go to safe place
        if len(weapons_pos) == 0:
            return None
        closest_good_weapon = \
            list(
                sorted(map(lambda pos: (pos, len(self.find_path(pos, bot_pos))), weapons_pos),
                       key=lambda item: item[1]))
        closest_good_weapon = [w for w in closest_good_weapon if w[1] > 0]
        if len(closest_good_weapon) == 0:
            return None
        return closest_good_weapon[0][0]

    def find_visible_enemies(self, bot_pos, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription], ):
        enemies_list = []
        for tile, description in visible_tiles.items():
            if description.character is not None and self.dist(tile, bot_pos) > 0:
                dist_to_enemy = len(self.find_path(bot_pos, tile))
                if dist_to_enemy <= self.enemy_range:
                    enemies_list.append((description, tile, dist_to_enemy))
        return sorted(enemies_list, key=lambda item: item[2])

    def find_direction(self, path_to_destination, knowledge, bot_pos):
        if len(path_to_destination) == 0:
            return random.choice([characters.Action.TURN_RIGHT, characters.Action.TURN_LEFT])
        for tile, description in knowledge.visible_tiles.items():
            distance = self.dist(bot_pos, tile)
            if distance == 1:
                current_tile = tile
                next_tile = path_to_destination[0]
                if next_tile == (current_tile[0], current_tile[1]):
                    return characters.Action.STEP_FORWARD
                x1 = next_tile[0] - bot_pos[0]
                y1 = next_tile[1] - bot_pos[1]
                x2 = current_tile[0] - bot_pos[0]
                y2 = current_tile[1] - bot_pos[1]
                angle = atan2(y2, x2) - atan2(y1, x1)
                if angle > 0:
                    return characters.Action.TURN_LEFT
                else:
                    return characters.Action.TURN_RIGHT
        return characters.Action.TURN_RIGHT

    def is_tile_valid(self, tile):
        if tile.type == 'land' or tile.type == 'menhir':
            return False
        loot = tile.loot
        weapons_prob = {'sword': 1.0, 'axe': 1.0, 'knife': 0.4, 'amulet': 0.05, 'bow_loaded': 0.1, 'bow_unloaded': 0.05}
        if loot:
            prob = weapons_prob[loot.name]
            r = random.uniform(0, 1)
            if r <= prob:
                return True
            return False
        return True

    def is_smaller(self, a, b):
        return a < b

    def is_greater(self, a, b):
        return a > b

    def update_knowledge(self, visible_tiles, bot_pos):
        # print(self.state, bot_pos, self.exploration_goal, self.current_strategy)
        for tile, description in visible_tiles.items():
            self.map[tile[0]][tile[1]] = description

            if tuple(tile) in self.unseen_coords:
                self.unseen_coords.remove(tuple(tile))
            if description.type == 'menhir':
                if WIETnamczyk.MIST_PANIC_MODE:
                    WIETnamczyk.MIST_PANIC_MODE = False
                    self.state = WIETnamczyk.GO_TO_MENHIR
                self.menhir_pos = tile
            if self.dist(tile, bot_pos) == 0:
                self.current_weapon = description.character.weapon
                if self.current_weapon == 'unloaded_bow':
                    self.action_queue.append(characters.Action.ATTACK)
                self.prev_hp = self.hp
                self.hp = description.character.health
                self.facing = description.character.facing
            if 'mist' in list(map(lambda d: d.type, description.effects)):
                def signum(a):
                    if a > 0:
                        return 1
                    if a == 0:
                        return 0
                    return -1

                sgn_bot_x = signum(bot_pos[0] - tile[0])
                sgn_bot_y = signum(bot_pos[1] - tile[1])
                to_remove = set()
                for unseen in self.unseen_coords:
                    sgn_uns_x = signum(tile[0] - unseen[0])
                    sgn_uns_y = signum(tile[1] - unseen[1])
                    if sgn_bot_x == sgn_uns_x and sgn_bot_y == sgn_uns_y:
                        to_remove.add(unseen)
                for u in to_remove:
                    self.unseen_coords.remove(u)
                # self.unseen_coords -= to_remove

    def parse_map(self, arena_name) -> List[List[tiles.TileDescription]]:
        arena = Arena.load(arena_name)
        map_matrix = [[None for i in range(arena.size[0])] for j in range(arena.size[1])]
        for k, v in arena.terrain.items():
            map_matrix[k[0]][k[1]] = v.description()
        return map_matrix

    def generate_coords(self):
        unseen_coords = set()
        for i, row in enumerate(self.map):
            for j, cell in enumerate(row):
                if cell.type in {'land', 'menhir'}:
                    unseen_coords.add((i, j))
        return unseen_coords

    def find_path(self, start_pos, dest_coord):
        X = len(self.map)
        Y = len(self.map)
        visited = [[False for _ in range(X)] for _ in range(Y)]
        parent = {start_pos: None}
        queue = deque([start_pos])

        while len(queue) > 0:
            s = queue.popleft()
            if s == dest_coord:
                path = []
                p = dest_coord
                while parent[p]:
                    path.append(p)
                    p = parent[p]
                return list(reversed(path))

            if not visited[s[0]][s[1]]:
                visited[s[0]][s[1]] = True
                for s_x, s_y in [(-1, 0), (1, 0), (0, 1), (0, -1)]:
                    adj_x = s[0] + s_x
                    adj_y = s[1] + s_y
                    adj = (adj_x, adj_y)
                    if self.can_pass(X, Y, adj_x, adj_y, visited):
                        queue.append(adj)
                        parent[adj] = s
        return []

    def can_pass(self, X, Y, adj_x, adj_y, visited):
        can_pass = 0 <= adj_x < X and 0 <= adj_y < Y and (
                self.map[adj_x][adj_y].type == 'land' or self.map[adj_x][adj_y].type == 'menhir') \
                   and not visited[adj_x][adj_y] and not (
                'mist' in list(map(lambda d: d.type, self.map[adj_x][adj_y].effects)))
        if can_pass and not WIETnamczyk.MIST_PANIC_MODE:
            if not self.map[adj_x][adj_y].loot:
                return can_pass
            return self.map[adj_x][adj_y].loot.name not in ['knife', 'amulet']
        return can_pass

    def go_to_menhir(self, knowledge: characters.ChampionKnowledge, bot_pos: Coords):
        path_to_destination = self.find_path(bot_pos, self.menhir_pos)
        return self.find_direction(path_to_destination, knowledge, bot_pos)

    def catharsis(self):
        self.action_queue = []

    def evaluate_mist(self, bot_pos: Coords, knowledge: characters.ChampionKnowledge):
        if WIETnamczyk.MIST_PANIC_MODE and self.find_path(bot_pos, self.exploration_goal) != []:
            # print("panic mode and I know what I need to do!")
            return
        for coords, desc in knowledge.visible_tiles.items():
            if desc.effects and 'mist' in list(map(lambda d: d.type, desc.effects)):
                if self.menhir_pos is not None:
                    self.state = WIETnamczyk.GO_TO_MENHIR
                    path_to_destination = self.find_path(bot_pos, self.menhir_pos)
                    return self.find_direction(path_to_destination, knowledge, bot_pos)
                else:
                    # todo: improve this logic :)
                    # print("I noticed mist and I am planning my next step, don't worry I am an adult!")
                    WIETnamczyk.MIST_PANIC_MODE = True
                    self.state = WIETnamczyk.EXPLORE
                    self.catharsis()
                    self.exploration_goal = random.choice(list(self.unseen_coords))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, WIETnamczyk):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    @profile
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        action = self.strategies_dict[self.current_strategy](knowledge)
        return action

    def set_exploration_area(self, bot_pos: Coords, max_dist_from_menhir=5):
        possible_cells = set()
        for i, row in enumerate(self.map):
            for j, cell in enumerate(row):
                if self.dist(bot_pos, Coords(i, j)) < max_dist_from_menhir:
                    possible_cells.add((i, j))
        self.unseen_coords = possible_cells
        self.exploration_goal = random.choice(list(possible_cells))

    def generate_enemy_avoidance_action(self):
        goals = [(self.dist(self.exploration_goal, cell), cell) for cell in self.unseen_coords]
        sorted_goals = sorted(goals, key=lambda item: item[0], reverse=True)
        self.exploration_goal = sorted_goals[0][1] if len(sorted_goals) != 0 else self.menhir_pos

        random_actions = random.choice(
            [[characters.Action.TURN_RIGHT],
             [characters.Action.TURN_RIGHT, characters.Action.TURN_RIGHT],
             [characters.Action.TURN_LEFT]])
        random_actions.append(characters.Action.STEP_FORWARD)
        self.action_queue.extend(random_actions)

        return self.action_queue.pop(0)

    def generate_panic_action(self, bot_pos: Coords, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, desc in visible_tiles.items():
            if self.dist(coords, bot_pos) == 1 and desc.type in ['land', 'menhir']:
                return characters.Action.STEP_FORWARD
        return random.choice([characters.Action.TURN_RIGHT, characters.Action.TURN_LEFT])

    def do_not_be_tabula_rasa(self, knowledge: characters.ChampionKnowledge):
        bot_pos = knowledge.position
        self.update_knowledge(knowledge.visible_tiles, bot_pos)
        self.evaluate_mist(bot_pos, knowledge)

    def stand_in_mist(self, visible_tiles, bot_pos):
        for coords, desc in visible_tiles.items():
            if self.dist(coords, bot_pos) == 0 and 'mist' in list(map(lambda d: d.type, desc.effects)):
                return True
        return False

    def perform_priority_checks(self, knowledge: characters.ChampionKnowledge):
        bot_pos = knowledge.position
        if self.should_attack(bot_pos, knowledge):
            return characters.Action.ATTACK
        if len(self.action_queue) != 0:
            return self.action_queue.pop(0)
        if self.prev_hp > self.hp:
            return self.generate_panic_action(bot_pos, knowledge.visible_tiles)
        return None

    def strategy_ostrich(self, knowledge: characters.ChampionKnowledge):
        """
        This version of the bot keeps looking for menhir unless it sees some weaker enemy, then it tries to kill it.
        """
        bot_pos = knowledge.position
        self.do_not_be_tabula_rasa(knowledge)
        priority_action = self.perform_priority_checks(knowledge)
        if priority_action:
            return priority_action

        if self.state == WIETnamczyk.GO_TO_MENHIR:
            if self.dist(bot_pos, self.menhir_pos) < 3:
                self.set_exploration_area(bot_pos)
                self.state = WIETnamczyk.EXPLORE
            else:
                return self.go_to_menhir(knowledge, bot_pos)

        if self.state == WIETnamczyk.GET_WEAPON:
            weapon_pos = self.find_good_weapon(bot_pos)
            if not weapon_pos or self.current_weapon.name in self.good_weapons:
                self.state = WIETnamczyk.EXPLORE
            else:
                path_to_destination = self.find_path((bot_pos[0], bot_pos[1]), (weapon_pos[0], weapon_pos[1]))
                return self.find_direction(path_to_destination, knowledge, bot_pos)

        if self.state == WIETnamczyk.EXPLORE:
            visible_enemies = self.find_visible_enemies(bot_pos, knowledge.visible_tiles)
            if len(visible_enemies) > 1:
                return self.generate_enemy_avoidance_action()
            if len(visible_enemies) == 1:
                enemy_pos = visible_enemies[0][1]
                enemy_tile_description = visible_enemies[0][0]
                if self.should_fight(bot_pos, enemy_pos, enemy_tile_description):
                    path_to_destination = self.find_path((bot_pos[0], bot_pos[1]), (enemy_pos[0], enemy_pos[1]))
                    return self.find_direction(path_to_destination, knowledge, bot_pos)
                return self.generate_enemy_avoidance_action()
            if len(self.unseen_coords) == 0:
                self.state = WIETnamczyk.GO_TO_MENHIR
                return random.choice(POSSIBLE_ACTIONS)
            return self.explore_map(bot_pos, knowledge)

        return random.choice(POSSIBLE_ACTIONS)

    def strategy_berserker(self, knowledge: characters.ChampionKnowledge):
        """
        Whenever the bot sees an enemy he immediately starts following him. Otherwise, it just explores the map and
        looks for the menhir.
        """
        bot_pos = knowledge.position
        self.do_not_be_tabula_rasa(knowledge)
        priority_action = self.perform_priority_checks(knowledge)
        if priority_action:
            return priority_action

        if self.state == WIETnamczyk.GET_WEAPON:
            weapon_pos = self.find_good_weapon(bot_pos)
            if not weapon_pos or self.current_weapon.name in self.good_weapons:
                self.state = WIETnamczyk.EXPLORE
            else:
                path_to_destination = self.find_path((bot_pos[0], bot_pos[1]), (weapon_pos[0], weapon_pos[1]))
                return self.find_direction(path_to_destination, knowledge, bot_pos)

        if self.state == WIETnamczyk.EXPLORE:
            visible_enemies = self.find_visible_enemies(bot_pos, knowledge.visible_tiles)
            if len(visible_enemies) > 0:
                enemy_pos = visible_enemies[0][1]
                enemy_tile_description = visible_enemies[0][0]
                path_to_destination = self.find_path((bot_pos[0], bot_pos[1]), (enemy_pos[0], enemy_pos[1]))
                return self.find_direction(path_to_destination, knowledge, bot_pos)
            if len(self.unseen_coords) == 0:
                self.state = WIETnamczyk.GO_TO_MENHIR
                return random.choice(POSSIBLE_ACTIONS)
            return self.explore_map(bot_pos, knowledge)

        if self.state == WIETnamczyk.GO_TO_MENHIR:
            if self.dist(bot_pos, self.menhir_pos) < 3:
                self.set_exploration_area(bot_pos)
                self.state = WIETnamczyk.EXPLORE
            else:
                return self.go_to_menhir(knowledge, bot_pos)

        return random.choice(POSSIBLE_ACTIONS)

    def strategy_coward(self, knowledge: characters.ChampionKnowledge):
        bot_pos = knowledge.position
        self.do_not_be_tabula_rasa(knowledge)
        priority_action = self.perform_priority_checks(knowledge)
        if priority_action:
            return priority_action

        if self.state in (WIETnamczyk.EXPLORE, WIETnamczyk.GET_WEAPON):
            visible_enemies = self.find_visible_enemies(bot_pos, knowledge.visible_tiles)
            if len(visible_enemies) > 0:
                return self.generate_enemy_avoidance_action()
            if len(self.unseen_coords) == 0:
                self.state = WIETnamczyk.GO_TO_MENHIR
                return random.choice(POSSIBLE_ACTIONS)
            return self.explore_map(bot_pos, knowledge)

        if self.state == WIETnamczyk.GO_TO_MENHIR:
            if self.dist(bot_pos, self.menhir_pos) < 3:
                self.set_exploration_area(bot_pos)
                self.state = WIETnamczyk.EXPLORE
            else:
                return self.go_to_menhir(knowledge, bot_pos)
        return random.choice(POSSIBLE_ACTIONS)

    def explore_map(self, current_position, knowledge):
        attempts = 5
        while self.exploration_goal is None or self.exploration_goal not in self.unseen_coords or \
                self.find_path(current_position, self.exploration_goal) == [] and attempts != 0:
            if WIETnamczyk.MIST_PANIC_MODE:
                WIETnamczyk.MIST_PANIC_MODE = False
            self.exploration_goal = random.choice(list(self.unseen_coords))
            attempts -= 1
        path_to_destination = self.find_path(current_position, self.exploration_goal)
        action = self.find_direction(path_to_destination, knowledge, current_position)
        return action

    def praise(self, score: int) -> None:
        self.N[self.current_strategy] += 1
        n = self.N[self.current_strategy]
        q = self.Q[self.current_strategy]
        self.Q[self.current_strategy] += (1 / n * (score - q))
        # only for tests
        # with open('wietnamczyk_q.json', 'w') as fp:
        #     json.dump(self.Q, fp)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.map: List[List[tiles.TileDescription]] = self.parse_map(arena_description.name)
        self.unseen_coords = self.generate_coords()

        self.arena_description = arena_description
        rand = random.uniform(0, 1)
        self.current_strategy = random.choice(self.strategies) if rand < WIETnamczyk.EPSILON else max(self.Q,
                                                                                                      key=self.Q.get)
        # print(self.Q)

    @property
    def name(self) -> str:
        return f'WIETnamczyk{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BLUE


POTENTIAL_CONTROLLERS = [
    WIETnamczyk(),
]
