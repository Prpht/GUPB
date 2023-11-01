import heapq
from gupb.controller.ancymon.environment import Environment
from gupb.model.coordinates import Coords

directions = [Coords(0, 1), Coords(0, -1), Coords(1, 0), Coords(-1, 0)]

class Path_Finder():
    def __init__(self, environment: Environment):
        self.environment: Environment = environment
    def heuristic(self, node: Coords, goal:Coords):
        # Calculate the Manhattan distance as the heuristic.
        return abs(node.x - goal.x) + abs(node.y - goal.y)

    def astar_search(self, start: Coords, end: Coords):
        open_set = [(0, start)]
        came_from = {}
        g_score = {Coords(row, col): float('inf') for row in range(self.environment.map_known_len) for col in range(self.environment.map_known_len)}
        g_score[start] = 0

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == end:
                path = self.reconstruct_path(came_from, end)
                return path

            for dCoord in directions:
                neighbor = current + dCoord
                if not self.is_valid(neighbor):
                    continue

                tentative_g_score = g_score[current] + 1  # Assuming a constant cost of 1 for movement.

                if tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score = tentative_g_score + self.heuristic(neighbor, end)
                    heapq.heappush(open_set, (f_score, neighbor))

        return None

    def is_valid(self, point):
        x, y = point
        if 0 <= x < self.environment.map_known_len and 0 <= y < self.environment.map_known_len:
            if self.environment.discovered_map.get(Coords(x, y)) == None:
                return True
            if self.environment.discovered_map[Coords(x, y)].type == 'land':
                return True
            if self.environment.discovered_map[Coords(x, y)].type == 'menhir':
                return True
        return False

    def reconstruct_path(self, came_from, current):
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.insert(0, current)
        return path

    # Example usage:
    def caluclate(self, start: Coords, end: Coords):

        path = self.astar_search(start, end)

        if path:
            return path
        else:
            print("No path found.")
            return None