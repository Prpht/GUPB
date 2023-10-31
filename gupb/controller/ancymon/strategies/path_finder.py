import heapq

# It is A* DEMO

directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

def heuristic(node, goal):
    # Calculate the Manhattan distance as the heuristic.
    return abs(node[0] - goal[0]) + abs(node[1] - goal[1])

def astar_search(grid, start, end):
    open_set = [(0, start)]
    came_from = {}
    g_score = {(row, col): float('inf') for row in range(len(grid)) for col in range(len(grid[0]))}
    g_score[start] = 0

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == end:
            path = reconstruct_path(came_from, end)
            return path

        for dx, dy in directions:
            neighbor = (current[0] + dx, current[1] + dy)
            if not is_valid(neighbor, grid):
                continue

            tentative_g_score = g_score[current] + 1  # Assuming a constant cost of 1 for movement.

            if tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score = tentative_g_score + heuristic(neighbor, end)
                heapq.heappush(open_set, (f_score, neighbor))

    return None  # No path found

def is_valid(point, grid):
    x, y = point
    return 0 <= x < len(grid) and 0 <= y < len(grid[0]) and grid[x][y] != 1

def reconstruct_path(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.insert(0, current)
    return path

# Example usage:
if __name__ == "__main__":
    grid = [
        [0, 0, 0, 1, 0],
        [0, 1, 1, 2, 0],
        [0, 2, 0, 1, 0],
        [0, 0, 0, 0, 0],
    ]

    start_x, start_y = 0, 0
    end_x, end_y = 3, 4

    start = (start_x, start_y)
    end = (end_x, end_y)

    path = astar_search(grid, start, end)

    if path:
        print("Path found:", path)
    else:
        print("No path found.")