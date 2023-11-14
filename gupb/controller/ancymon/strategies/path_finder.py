import heapq
from gupb.controller.ancymon.environment import Environment
from gupb.model.coordinates import Coords
from gupb.model import characters

directions = [Coords(0, 1), Coords(0, -1), Coords(1, 0), Coords(-1, 0)]

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

class Path_Finder():
    def __init__(self, environment: Environment):
        self.environment: Environment = environment
        self.g_score = None
        self.came_from = None
        self.avoid_players: bool = False

    def update_paths(self, start: Coords, avoid_enemies: bool = False):
        open_set = [(0, start)]
        self.came_from = {}
        self.g_score = {Coords(row, col): float('inf') for row in range(self.environment.map_known_len+1) for col in range(self.environment.map_known_len+1)}
        self.g_score[start] = 0
        self.avoid_players = avoid_enemies

        while open_set:
            _, current = heapq.heappop(open_set)

            for dCoord in directions:
                neighbor = current + dCoord
                if not self.is_valid(neighbor):
                    continue

                tentative_g_score = self.g_score[current] + 1

                if tentative_g_score < self.g_score[neighbor]:
                    self.came_from[neighbor] = current
                    self.g_score[neighbor] = tentative_g_score
                    f_score = tentative_g_score
                    heapq.heappush(open_set, (f_score, neighbor))

    def is_valid(self, point):
        x, y = point
        if 0 <= x <= self.environment.map_known_len and 0 <= y <= self.environment.map_known_len:
            if self.environment.discovered_map.get(point) == None:
                return True
            if self.avoid_players and self.environment.discovered_map.get(point).character and self.environment.discovered_map.get(point).character.health > self.environment.champion.health:
                return False
            if self.environment.discovered_map.get(point).type == 'land':
                return True
            if self.environment.discovered_map.get(point).type == 'menhir':
                return True
        return False

    def reconstruct_path(self, current):
        path = [current]
        while current in self.came_from:
            current = self.came_from[current]
            path.insert(0, current)
        return path

    def calculate_path_length(self, end: Coords):
        path = self.reconstruct_path(end)

        if path:
            return len(path) - 1
        return float('inf')


    def calculate_next_move(self, end: Coords):
        start = self.environment.position
        path = self.reconstruct_path(end)

        if path and len(path) >= 3:
            if self.environment.champion.facing.value == Coords(1, 0):
                if self.environment.position + Coords(0,1) == path[1] and self.environment.position + Coords(1,1) == path[2]:
                    return characters.Action.STEP_RIGHT, path
                if self.environment.position + Coords(0,-1) == path[1] and self.environment.position + Coords(1, -1) == path[2]:
                    return characters.Action.STEP_LEFT, path
            if self.environment.champion.facing.value == Coords(0, 1):
                if self.environment.position + Coords(1, 0) == path[1] and self.environment.position + Coords(1, 1) == path[2]:
                    return characters.Action.STEP_LEFT, path
                if self.environment.position + Coords(-1, 0) == path[1] and self.environment.position + Coords(-1, 1) == path[2]:
                    return characters.Action.STEP_RIGHT, path
            if self.environment.champion.facing.value == Coords(-1, 0):
                if self.environment.position + Coords(0,1) == path[1] and self.environment.position + Coords(-1,1) == path[2]:
                    return characters.Action.STEP_LEFT, path
                if self.environment.position + Coords(0,-1) == path[1] and self.environment.position + Coords(-1, -1) == path[2]:
                    return characters.Action.STEP_RIGHT, path
            if self.environment.champion.facing.value == Coords(0, -1):
                if self.environment.position + Coords(1, 0) == path[1] and self.environment.position + Coords(1, -1) == path[2]:
                    return characters.Action.STEP_RIGHT, path
                if self.environment.position + Coords(-1, 0) == path[1] and self.environment.position + Coords(-1, -1) == path[2]:
                    return characters.Action.STEP_LEFT, path

        if path and len(path) > 1:
            next_move = path[1]
            move_vector = next_move - start
            sub = self.environment.champion.facing.value - move_vector

            if sub.x != 0 or sub.y != 0:
                if sub.x == 2 or sub.y == 2 or sub.x == -2 or sub.y == -2:
                    return characters.Action.TURN_RIGHT, path

                if move_vector.x == 0:
                    if sub.x * sub.y == 1:
                        return characters.Action.TURN_LEFT, path
                    else:
                        return characters.Action.TURN_RIGHT, path

                if move_vector.y == 0:
                    if sub.x * sub.y == 1:
                        return characters.Action.TURN_RIGHT, path
                    else:
                        return characters.Action.TURN_LEFT, path

            return characters.Action.STEP_FORWARD, path
        else:
            return None, None
