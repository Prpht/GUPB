import os
import random
import numpy as np
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena

from gupb.model.characters import Facing
from gupb.model import coordinates

from numpy import empty, sqrt, square
from scipy.linalg import lstsq


class ShrekController:
    def __init__(self, first_name: str):
        self.points_to_visit = None
        self.first_name: str = first_name
        self.position = None
        self.weapon_name = 'knife'
        self.menhir = None
        self.path = []
        self.tactic_spots = []
        self.facing = None
        self.map = None
        self.goal = None
        self.map_corners = []
        self.hiding_spot = None
        self.emergency_steps = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ShrekController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.position = None
        self.facing = None
        self.weapon_name = 'knife'
        self.map, self.tactic_spots = self.load_map(arena_description.name)
        self.goal = None
        self.path = []
        self.points_to_visit = self.find_spots_to_visit()
        self.map_corners = self.points_to_visit[:]
        self.menhir = None
        self.hiding_spot = None
        self.tactic_spots = []
        self.emergency_steps = []

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.position = knowledge.position
        info = knowledge.visible_tiles[self.position].character
        self.facing = info.facing
        self.weapon_name = info.weapon.name

        if self.is_enemy_around(knowledge):
            facing_tile = self.position + self.facing.value  # if we face character we fight
            if knowledge.visible_tiles[facing_tile].character and self.weapon_name != 'amulet':
                return characters.Action.ATTACK

            if self.weapon_name == 'sword':  # if we have sword we fight the characters if they are 3 tiles in front of us
                facing_tile2 = facing_tile + self.facing.value
                facing_tile3 = facing_tile2 + self.facing.value

                if facing_tile2 in knowledge.visible_tiles:
                    if knowledge.visible_tiles[facing_tile2].character:
                        return characters.Action.ATTACK

                if facing_tile3 in knowledge.visible_tiles:
                    if knowledge.visible_tiles[facing_tile3].character:
                        return characters.Action.ATTACK

            if self.should_attack(self.position, knowledge):
                return characters.Action.ATTACK

        if len(self.emergency_steps) > 0:
            wanted_field = coordinates.Coords(self.emergency_steps[0][0], self.emergency_steps[0][1])
            substract_points = coordinates.sub_coords(wanted_field, self.position)
            needed_facing = Facing(substract_points)
            if self.facing == needed_facing:
                self.emergency_steps.pop(0)
                return characters.Action.STEP_FORWARD
            else:
                return characters.Action.TURN_RIGHT

        if self.am_i_on_hiding_spot():
            if self.mist_comes(knowledge):
                self.emergency_steps = self.find_path(self.menhir)
            return characters.Action.TURN_RIGHT

        try:
            if self.am_i_on_menhir() and not self.hiding_spot:
                return characters.Action.TURN_RIGHT

            else:
                if not self.hiding_spot:
                    if self.do_i_see_menhir(knowledge.visible_tiles, knowledge.position):
                        self.hiding_spot = self.find_hiding_spot_around(self.menhir)
                        if self.hiding_spot:
                            self.goal = self.hiding_spot
                        else:

                            self.do_i_see_menhir(knowledge.visible_tiles, knowledge.position)
                        self.set_path(knowledge)
                elif self.mist_comes(knowledge):
                    self.goal = self.find_further_point()
                    self.set_path(knowledge)
                    self.hiding_spot = None
                elif self.do_i_see_mist(knowledge):
                    self.run_from_mist(knowledge)
                    self.set_path(knowledge)
                    self.hiding_spot = None
                if self.tactic_spots and self.goal is None:
                    self.find_closest_weapon()
                    self.set_path(knowledge)

            if self.path:
                wanted_field = coordinates.Coords(self.path[0][0], self.path[0][1])
                substract_points = coordinates.sub_coords(wanted_field, self.position)
                needed_facing = Facing(substract_points)
                if self.facing == needed_facing:
                    self.path.pop(0)
                    return characters.Action.STEP_FORWARD
                else:
                    return characters.Action.TURN_RIGHT


            else:
                self.goal = self.find_closest_point()
                if self.goal in self.points_to_visit:
                    self.points_to_visit.remove(self.goal)

                self.set_path(knowledge)
        except:
            if not self.goal:
                self.goal = self.find_further_point()
                self.set_path(knowledge)

        return characters.Action.TURN_RIGHT

    """
    Here are the functions we use:
    """

    def take_step_from_path(self, path):
        wanted_field = coordinates.Coords(path[0][0], path[0][1])
        substract_points = coordinates.sub_coords(wanted_field, self.position)
        needed_facing = Facing(substract_points)
        if self.facing == needed_facing:
            path.pop(0)
            # check 3 fields next to goal if someone is there:
            return characters.Action.STEP_FORWARD
        else:
            return characters.Action.TURN_RIGHT

    def find_hiding_spot_around(self, position):
        width_map = len(self.map[0])
        height_map = len(self.map)

        x_1 = max(0, position[0] - int(width_map // 7))
        x_2 = min(width_map, position[0] + int(width_map // 7))

        y_1 = max(0, position[1] - int(height_map // 7))
        y_2 = min(height_map, position[1] + int(height_map // 7))

        sub_optimal = None

        for i in range(x_1, x_2 + 1):
            for j in range(y_1, y_2 + 1):
                if self.map[j][i] == 1:
                    neighbouring_walls = 0

                    for dx, dy in [[0, 1], [0, -1], [1, 0], [-1, 0]]:
                        nx, ny = j + dx, i + dy
                        if self.map[nx][ny] == 0:
                            #  nx not in range(width_map) or ny not in range(height_map) or self.map[nx][ny] == 0:
                            neighbouring_walls += 1

                    if neighbouring_walls == 3:
                        return i, j

                # if neighbouring_walls == 2:
                #     sub_optimal = i, j

        return sub_optimal

    def should_attack(self, self_pos: coordinates.Coords, knowledge: characters.ChampionKnowledge):
        if self.weapon_name in ['bow_loaded', 'bow_unloaded']:
            for tile, description in knowledge.visible_tiles.items():
                distance = self.get_distance(tile, self_pos)
                if distance == 0 or description.character is None:
                    continue
                if (self.facing == Facing.UP or self.facing == Facing.DOWN) and (tile[0] - self_pos[0]) == 0:
                    return True
                if (self.facing == Facing.LEFT or self.facing == Facing.RIGHT) and (tile[1] - self_pos[1]) == 0:
                    return True
            return False

        if self.weapon_name == 'amulet':
            attack_tiles = [coordinates.Coords(self.position.x + 1, self.position.y + 1),
                            coordinates.Coords(self.position.x - 1, self.position.y - 1),
                            coordinates.Coords(self.position.x + 1, self.position.y - 1),
                            coordinates.Coords(self.position.x - 1, self.position.y + 1),
                            coordinates.Coords(self.position.x - 2, self.position.y + 2),
                            coordinates.Coords(self.position.x - 2, self.position.y - 2),
                            coordinates.Coords(self.position.x + 2, self.position.y - 2),
                            coordinates.Coords(self.position.x + 2, self.position.y + 2)]

            for tile, description in knowledge.visible_tiles.items():
                if tile in attack_tiles and description.character:
                    return True
            return False

    def is_enemy_around(self, knowledge: characters.ChampionKnowledge):
        """
        Check if any enemies in sight
        """
        for coord, tile_descr in knowledge.visible_tiles.items():
            if tile_descr.character and coord != (self.position.x, self.position.y):
                return True
        return False

    def am_i_on_hiding_spot(self):
        """
               Check if bot is on the hiding_spot
        """
        if self.hiding_spot:
            cords = coordinates.Coords(self.hiding_spot[0], self.hiding_spot[1])
            if self.position.x == cords.x and self.position.y == cords.y:
                return True
        return False

    def get_distance(self, cord1: coordinates.Coords, cord2: coordinates.Coords):
        if not cord1 or not cord2:
            return 0
        dist = abs(cord1[0] - cord2[0]) + abs(cord1[1] - cord2[1])
        return dist

    def get_max_distance(self, cord1: coordinates.Coords, cord2: coordinates.Coords):
        return max(abs(cord1[0] - cord2[0]), abs(cord1[1] - cord2[1]))

    def am_i_on_menhir(self):
        """
               Check if bot is on the mehir
        """
        if self.menhir is not None:
            cords = coordinates.Coords(self.menhir[0], self.menhir[1])
            if self.position.x == cords.x and self.position.y == cords.y:
                return True
        return False

    def do_i_see_menhir(self, visible_tiles, position):
        """
               Check if bot sees the menhir
        """
        for coordinate, tile_descr in visible_tiles.items():
            if tile_descr.type == 'menhir':
                self.goal = coordinate[0], coordinate[1]
                self.menhir = self.goal
                return True
        return False

    def set_path(self, knowledge: characters.ChampionKnowledge):
        """
               Remember the path to menhir
        """
        self.path = self.find_path(self.goal)

    def find_spots_to_visit(self):
        width = len(self.map[0]) - 1
        height = len(self.map) - 1

        points = [(0, 0), (0, width), (height, 0), (height, width)]
        new_points = []
        for i, p in enumerate(points):
            x, y = p[0], p[1]
            while self.map[x][y] == 0:
                if i == 0:
                    x += 1
                    y += 1
                elif i == 1:
                    x += 1
                    y -= 1
                elif i == 2:
                    x -= 1
                    y += 1
                else:
                    x -= 1
                    y -= 1
            if 0 <= x <= width and height >= y >= 0:
                new_points.append((x, y))
        return new_points

    def find_closest_point(self):
        """
        Find the closest point to bot
        """
        distances = {}
        for p in self.points_to_visit:
            distances[p] = self.get_distance((self.position.x, self.position.y), p)
        if distances:
            return min(distances, key=distances.get)

    def find_further_point(self):
        """
        Find the closest point to bot
        """
        distances = {}
        for p in self.map_corners:
            distances[p] = self.get_distance((self.goal[0], self.goal[1]), p)
        return max(distances, key=distances.get)

    def get_distance(self, coords_a, coords_b):
        return ((coords_a[0] - coords_b[0]) ** 2 + (coords_a[1] - coords_b[1]) ** 2) ** 0.5

    def load_map(self, map_name):
        """
        Load the map
        """
        tactic_spots = []
        arena = Arena.load(map_name)
        map_matrix = [[1 for x in range(arena.size[0])] for y in range(arena.size[1])]
        for cords, tile in arena.terrain.items():
            map_matrix[cords.y][cords.x] = 0 if tile.description().type in ['wall', 'sea'] else 1
            if tile.description().loot:
                # map_matrix[cords.x][cords.y] = 0 if tile.description().loot.name in ["knife", "amulet", "bow_unloaded"] else 1
                if tile.description().loot.name in ["axe", "sword", 'bow_loaded', 'bow_unloaded']:
                    tactic_spots.append((cords.x, cords.y))
        return map_matrix, tactic_spots

    def find_path(self, destination):
        """
        Find the path to current destination
        """
        grid = Grid(matrix=self.map)
        start = grid.node(self.position[0], self.position[1])
        end = grid.node(destination[0], destination[1])
        finder = AStarFinder()
        path, runs = finder.find_path(start, end, grid)
        if len(path) > 0:
            path.pop(0)
        return path

    def move(self):
        """
        Take a step forward, or turn
        """
        rand_num = random.random()
        if rand_num <= 0.8:
            return characters.Action.STEP_FORWARD
        elif rand_num > 0.8 and rand_num <= 0.9:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT

    def find_closest_weapon(self):
        """
        Decide which weapon is the closest and go to it(only include the axe and sword)
        """
        min_path_len = 10000
        closest_weapon = ()
        for weapon in self.tactic_spots:
            weapon_len = len(self.find_path(weapon))
            if weapon_len < min_path_len:
                closest_weapon = weapon
                min_path_len = weapon_len
        self.tactic_spots = []
        self.goal = closest_weapon

    def mist_comes(self, knowledge: characters.ChampionKnowledge):
        """
        Check if there is mist nearby (facing 4 tiles)
        """
        facing_tile = self.position + self.facing.value
        for x in range(5):
            if facing_tile in knowledge.visible_tiles:
                if knowledge.visible_tiles[facing_tile].effects:
                    for effect in knowledge.visible_tiles[facing_tile].effects:
                        if effect.type == 'mist':
                            return True
            facing_tile += self.facing.value
        return False

    def do_i_see_mist(self, knowledge: characters.ChampionKnowledge):
        for tile in knowledge.visible_tiles:
            if knowledge.visible_tiles[tile].effects:
                for effect in knowledge.visible_tiles[tile].effects:
                    if effect.type == 'mist':
                        return True
        return False

    def run_from_mist(self, knowledge: characters.ChampionKnowledge):
        width = len(self.map[0]) - 1
        height = len(self.map) - 1
        data = []
        for tile in knowledge.visible_tiles:
            if knowledge.visible_tiles[tile].effects:
                for effect in knowledge.visible_tiles[tile].effects:
                    if effect.type == 'mist':
                        data.append(tile)
        border = []
        for mist in data:
            add = False
            neighbours = [(mist[0], mist[1] + 1), (mist[0], mist[1] - 1), (mist[0] + 1, mist[1]),
                          (mist[0] - 1, mist[1])]
            for n in neighbours:
                if n in knowledge.visible_tiles:
                    if not knowledge.visible_tiles[n].effects:
                        add = True
            if add:
                border.append((mist[0], height - mist[1]))
        if len(border) > 0:
            r, c = self.nsphere_fit(border)
            coords = (int(c[0]), int(c[1]))
            if 0 < coords[0] < width and 0 < coords[1] < height:
                if self.map[coords[0]][coords[1]] == 0:
                    self.path = self.find_path(coords)

    def nsphere_fit(self, x, axis=-1):
        height = len(self.map) - 1
        x = np.array(x)
        n = x.shape[-1]
        x = x.reshape(-1, n)
        m = x.shape[0]

        B = empty((m, n + 1), dtype=x.dtype)
        X = B[:, :-1]
        X[:] = x
        B[:, -1] = 1

        d = square(X).sum(axis=-1)

        y, *_ = lstsq(B, d, overwrite_a=True, overwrite_b=True)

        c = 0.5 * y[:-1]
        r = sqrt(y[-1] + square(c).sum())

        return r, c

    def go_nuts(self):
        width = len(self.map[0]) - 1
        height = len(self.map) - 1
        for t in range(0, 10):
            coords = (self.menhir[0] + random.randint(0, 4), self.menhir[1] + random.randint(0, 4))
            if 0 < coords[0] < width and 0 < coords[1] < height:
                if self.map[coords[0]][coords[1]] == 0:
                    return coords
        return self.menhir

    def praise(self, score: int) -> None:
        pass

    @property
    def name(self) -> str:
        return f'ShrekController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN


POTENTIAL_CONTROLLERS = [
    ShrekController("Fiona"),
]