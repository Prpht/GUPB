from typing import Tuple, List
import heapq
from gupb.model.arenas import Arena
from gupb.model import coordinates

class PathFinder():
    def __init__(self, arena: Arena) -> None:
        self.initialize_grid(arena)
        self.rows = arena.size[0]
        self.cols = arena.size[1]


    def initialize_grid(self, arena: Arena) -> None:
        self.grid = [[0 for _ in range(arena.size[1])] for _ in range(arena.size[0])]
        for coord in arena.terrain:
            tile = arena.terrain[coord]
            if tile.terrain_passable():
                self.grid[coord[0]][coord[1]] = 0
            else:
                self.grid[coord[0]][coord[1]] = 1


    def find_the_shortest_path(self, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        if start == end:
            return [start]
        
        open_heap = []
        heapq.heappush(open_heap, (self.manhattan(start, end), 0, start))
        
        came_from = {}
        g_scores = {start: 0}
        
        while open_heap:
            current_f, current_g, current_node = heapq.heappop(open_heap)
            
            if current_node == end:
                return self.reconstruct_path(came_from, current_node)
            
            if current_g > g_scores.get(current_node, float('inf')):
                continue
            
            for neighbor in self.get_neighbors(current_node):
                tentative_g = current_g + 1
                if tentative_g < g_scores.get(neighbor, float('inf')):
                    came_from[neighbor] = current_node
                    g_scores[neighbor] = tentative_g
                    f_score = tentative_g + self.manhattan(neighbor, end)
                    heapq.heappush(open_heap, (f_score, tentative_g, neighbor))
        return []


    def manhattan(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
    
    def get_neighbors(self, node: Tuple[int, int]) -> List[Tuple[int, int]]:
        x, y = node
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if self.is_valid(nx, ny):
                neighbors.append((nx, ny))
        return neighbors
    
    def is_valid(self, x: int, y: int) -> bool:
        return 0 <= x < self.rows and 0 <= y < self.cols and self.grid[x][y] == 0
    
    def reconstruct_path(self, came_from: dict, current: Tuple[int, int]) -> List[coordinates.Coords]:
        path = [coordinates.Coords(*current)]
        while current in came_from:
            current = came_from[current]
            path.append(coordinates.Coords(*current))
        path.reverse()
        return path