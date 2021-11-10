import logging
import random
from math import atan2
from collections import deque

from gupb import controller
from gupb.controller.random import POSSIBLE_ACTIONS
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import Facing
from gupb.model.coordinates import Coords

from typing import List, Dict


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class WIETnamczyk(controller.Controller):
    GET_WEAPON = "get_weapon"
    EXPLORE = "explore"
    PANIC = "panic"

    def __init__(self):
        self.mist_range = 3
        self.enemy_range = 8

        self.menhir_pos = None
        self.good_weapons = ["sword", "axe"]
        self.first_name: str = "Adam"
        self.map: List[List[tiles.TileDescription]] = self.parse_map()
        self.unseen_coords = self.generate_coords()
        self.arena_description = None
        self.current_weapon = "knife"
        self.state = WIETnamczyk.GET_WEAPON
        self.next_dest = None
        self.hp = None
        self.facing = None
        self.exploration_goal = None

    def dist(self, tile1: coordinates.Coords, tile2: coordinates.Coords):
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
        weapon_reach = {'sword': 3, 'axe': 1, 'knife': 1, 'bow': float('inf')}
        if self.current_weapon.name not in ['bow', 'amulet']:
            bfs_distance = self.bfs_dist(self_pos, enemy_pos)
            max_dist = weapon_reach[self.current_weapon.name] + 1
            if enemy_hp < self.hp:
                return False
            if bfs_distance <= max_dist:
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
        if self.current_weapon.name == 'bow':
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
        return closest_good_weapon[0][0]

    def find_visible_enemies(self, bot_pos, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription], ):
        enemies_list = []
        for tile, description in visible_tiles.items():
            if description.character is not None:
                dist_to_enemy = len(self.find_path(bot_pos, tile))
                if dist_to_enemy <= self.enemy_range:
                    enemies_list.append((description, tile))
        return enemies_list

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

    def evaluate_mist(self, current_pos, knowledge):
        for tile, description in knowledge.visible_tiles.items():
            if self.max_dist(tile, current_pos) <= self.mist_range:
                if 'mist' in list(map(lambda item: item.type, description.effects)):
                    self.safe_places = self.inner_places
                    self.prob = self.inner_prob

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

    def update_knowledge(self, visible_tiles, bot_pos):
        for tile, description in visible_tiles.items():
            self.unseen_coords.remove(tile)
            self.map[tile[0]][tile[1]] = description
            if description.type == 'menhir':
                self.menhir_pos = tile
            if self.dist(tile, bot_pos) == 0:
                self.current_weapon = description.character.weapon
                self.hp = description.character.health
                self.facing = description.character.facing

    def parse_map(self) -> List[List[tiles.TileDescription]]:
        arena = Arena.load("isolated_shrine")
        map_matrix = [[None for i in range(arena.size[0])] for j in range(arena.size[1])]
        for k, v in arena.terrain.items():
            map_matrix[k[0]][k[1]] = v.description()
        return map_matrix

    def generate_coords(self):
        unseen_coords = set()
        for i, row in enumerate(self.map):
            for j, cell in enumerate(row):
                if cell.type in {'land', 'menhir'}:
                    unseen_coords.add(Coords(i, j))
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
                    if 0 <= adj_x < X and 0 <= adj_y < Y and (
                            self.map[adj_x][adj_y].type == 'land' or self.map[adj_x][
                        adj_y].type == 'menhir') and not \
                            visited[adj_x][
                                adj_y]:
                        queue.append(adj)
                        parent[adj] = s
        return []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, WIETnamczyk):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        bot_pos = knowledge.position
        self.update_knowledge(knowledge.visible_tiles, bot_pos)
        self.evaluate_mist(bot_pos, knowledge)

        if self.should_attack(bot_pos, knowledge):
            return characters.Action.ATTACK

        if self.state == WIETnamczyk.EXPLORE:
            visible_enemies = self.find_visible_enemies(bot_pos, knowledge.visible_tiles)
            if len(visible_enemies) > 1:
                # TODO implement enemy avoidance
                return characters.Action.TURN_RIGHT
            if len(visible_enemies) == 1:
                enemy_pos = visible_enemies[0][1]
                enemy_tile_description = visible_enemies[0][0]
                if self.should_fight(bot_pos, enemy_pos, enemy_tile_description):
                    path_to_destination = self.find_path((bot_pos[0], bot_pos[1]), (enemy_pos[0], enemy_pos[1]))
                    return self.find_direction(path_to_destination, knowledge, bot_pos)
            return self.explore_map(bot_pos, knowledge)

        if self.state == WIETnamczyk.GET_WEAPON:
            weapon_pos = self.find_good_weapon(bot_pos)
            if not weapon_pos or self.current_weapon.name in self.good_weapons:
                self.state = WIETnamczyk.EXPLORE
            else:
                path_to_destination = self.find_path((bot_pos[0], bot_pos[1]), (weapon_pos[0], weapon_pos[1]))
                return self.find_direction(path_to_destination, knowledge, bot_pos)

        return random.choice(POSSIBLE_ACTIONS)

    def explore_map(self, current_position, knowledge):
        if self.exploration_goal is None or self.exploration_goal not in self.unseen_coords:
            self.exploration_goal = random.choice(self.unseen_coords)
        path_to_destination = self.find_path(current_position, self.exploration_goal)
        return self.find_direction(path_to_destination, knowledge, current_position)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.arena_description = arena_description

    @property
    def name(self) -> str:
        return f'WIETnamczyk{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BLUE


POTENTIAL_CONTROLLERS = [
    WIETnamczyk(),
]
