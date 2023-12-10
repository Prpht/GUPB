import heapq
import math
from gupb.model.coordinates import Coords

class PathFinder:
    def __init__(self, map):
        self.map = map

    @staticmethod
    def find_nearest_path( grid, start, goal):
    # Inicjalizuj listę odwiedzonych pozycji
        if goal is None:
            return None
        visited_positions = set()

        # Inicjalizuj kolejkę priorytetową do przechowywania pozycji i ich kosztów
        priority_queue = [(0, start, [])]  # (koszt, pozycja, ścieżka)

        while priority_queue:
            cost, current_position, path = heapq.heappop(priority_queue)

            if current_position == goal:
                return path  # Znaleziono cel, zwróć ścieżkę

            if current_position in visited_positions:
                continue  # Ta pozycja została już odwiedzona

            visited_positions.add(current_position)

            # Oblicz dostępne pozycje i ich koszty
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                new_position = (current_position[0] + dx, current_position[1] + dy)
                if new_position in grid:
                    new_cost = len(path) + 1 + math.dist(new_position, goal)
                    heapq.heappush(priority_queue, (new_cost, new_position, path + [new_position]))
        return None  # Nie znaleziono ścieżki do celu
    
    @staticmethod
    def find_shortest_path_from_list(paths):
        not_empty_paths = [path for path in paths if path is not None]  # Fixed the list comprehension
        if not not_empty_paths:
            return None  # Return None if the list is empty
        shortest_path = min(not_empty_paths, key=len)
        return shortest_path
    
    @staticmethod
    def calculate_direction(from_position, to_position):
        # Oblicz kierunek między dwiema pozycjami
        direction = Coords(to_position[0] - from_position[0], to_position[1] - from_position[1])
        return direction
    @staticmethod
    def is_opposite_direction(direction1, direction2):
        # Sprawdź, czy dwie koordynaty są przeciwne sobie
        return  direction1[0] == -direction2[0] and direction1[1] == -direction2[1]
