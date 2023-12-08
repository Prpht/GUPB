import heapq
from gupb.controller.ancymon.environment import Environment
from gupb.model.coordinates import Coords
from gupb.model import characters

directions = [Coords(0, 1), Coords(0, -1), Coords(1, 0), Coords(-1, 0)]

class Path_Finder():
    def __init__(self, environment: Environment, avoid_obstacles: bool = False):
        self.environment: Environment = environment
        self.g_score = None
        self.came_from = None
        self.avoid_obstacles: bool = avoid_obstacles

    def update_paths(self, start: Coords):
        open_set = [(0, start)]
        self.came_from = {}
        self.g_score = {Coords(row, col): float('inf') for row in range(self.environment.map_known_len+1) for col in range(self.environment.map_known_len+1)}
        self.g_score[start] = 0

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
                    heapq.heappush(open_set, (tentative_g_score, neighbor))

    def is_valid(self, point):
        x, y = point
        if 0 <= x <= self.environment.map_known_len and 0 <= y <= self.environment.map_known_len:
            field = self.environment.discovered_map.get(point)
            if field is None:
                return True
            if self.avoid_obstacles and field.character and field.character.controller_name != self.environment.champion.controller_name:
                return False
            if self.avoid_obstacles and self.environment.weapon.name != 'knife' and field.loot is not None and field.loot.name.find('bow') >= 0:
                return False
            if field.type == 'land':
                return True
            if field.type == 'menhir':
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

    def next_action(self, path: list[Coords], fast_move: bool = False)-> characters.Action:
        start = self.environment.position

        if path and len(path) >= 3:
            if self.environment.champion.facing.value == Coords(1, 0):
                if self.environment.position + Coords(0, 1) == path[1] and self.environment.position + Coords(1,1) == path[2]:
                    return characters.Action.STEP_RIGHT
                if self.environment.position + Coords(0,-1) == path[1] and self.environment.position + Coords(1, -1) == path[2]:
                    return characters.Action.STEP_LEFT
            if self.environment.champion.facing.value == Coords(0, 1):
                if self.environment.position + Coords(1, 0) == path[1] and self.environment.position + Coords(1, 1) == path[2]:
                    return characters.Action.STEP_LEFT
                if self.environment.position + Coords(-1, 0) == path[1] and self.environment.position + Coords(-1, 1) == path[2]:
                    return characters.Action.STEP_RIGHT
            if self.environment.champion.facing.value == Coords(-1, 0):
                if self.environment.position + Coords(0,1) == path[1] and self.environment.position + Coords(-1,1) == path[2]:
                    return characters.Action.STEP_LEFT
                if self.environment.position + Coords(0,-1) == path[1] and self.environment.position + Coords(-1, -1) == path[2]:
                    return characters.Action.STEP_RIGHT
            if self.environment.champion.facing.value == Coords(0, -1):
                if self.environment.position + Coords(1, 0) == path[1] and self.environment.position + Coords(1, -1) == path[2]:
                    return characters.Action.STEP_RIGHT
                if self.environment.position + Coords(-1, 0) == path[1] and self.environment.position + Coords(-1, -1) == path[2]:
                    return characters.Action.STEP_LEFT

        if path and len(path) > 1 and fast_move:
            next_move = path[1]
            move_vector = next_move - start

            if self.environment.champion.facing.value == Coords(1, 0):
                if move_vector == Coords(1, 0):
                    return characters.Action.STEP_FORWARD
                if move_vector == Coords(0, 1):
                    return characters.Action.STEP_RIGHT
                if move_vector == Coords(-1, 0):
                    return characters.Action.STEP_BACKWARD
                if move_vector == Coords(0, -1):
                    return characters.Action.STEP_LEFT
            if self.environment.champion.facing.value == Coords(0, 1):
                if move_vector == Coords(1, 0):
                    return characters.Action.STEP_LEFT
                if move_vector == Coords(0, 1):
                    return characters.Action.STEP_FORWARD
                if move_vector == Coords(-1, 0):
                    return characters.Action.STEP_RIGHT
                if move_vector == Coords(0, -1):
                    return characters.Action.STEP_BACKWARD
            if self.environment.champion.facing.value == Coords(-1, 0):
                if move_vector == Coords(1, 0):
                    return characters.Action.STEP_BACKWARD
                if move_vector == Coords(0, 1):
                    return characters.Action.STEP_LEFT
                if move_vector == Coords(-1, 0):
                    return characters.Action.STEP_FORWARD
                if move_vector == Coords(0, -1):
                    return characters.Action.STEP_RIGHT
            if self.environment.champion.facing.value == Coords(0, -1):
                if move_vector == Coords(1, 0):
                    return characters.Action.STEP_RIGHT
                if move_vector == Coords(0, 1):
                    return characters.Action.STEP_BACKWARD
                if move_vector == Coords(-1, 0):
                    return characters.Action.STEP_LEFT
                if move_vector == Coords(0, -1):
                    return characters.Action.STEP_FORWARD

        if path and len(path) > 1:
            next_move = path[1]
            move_vector = next_move - start
            sub = self.environment.champion.facing.value - move_vector

            if sub.x != 0 or sub.y != 0:
                if sub.x == 2 or sub.y == 2 or sub.x == -2 or sub.y == -2:
                    return characters.Action.TURN_RIGHT

                if move_vector.x == 0:
                    if sub.x * sub.y == 1:
                        return characters.Action.TURN_LEFT
                    else:
                        return characters.Action.TURN_RIGHT

                if move_vector.y == 0:
                    if sub.x * sub.y == 1:
                        return characters.Action.TURN_RIGHT
                    else:
                        return characters.Action.TURN_LEFT

            return characters.Action.STEP_FORWARD
        else:
            return None

    def calculate_next_move(self, end: Coords):
        path = self.reconstruct_path(end)
        action = self.next_action(path)
        return action, path
