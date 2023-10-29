def find_nearest_path(grid, start, goal):
    # Initialize a list to represent the path
    grid.add(start)
    grid.add(goal)
    print(grid)
    path = [start]
    current_position = start
    current_direction = (0, 1)  # Initially facing up

    while current_position != goal:
        # Calculate the positions for moving forward, turning right, and turning left
        forward_position = (current_position[0] + current_direction[0], current_position[1] + current_direction[1])
        right_position = (current_position[0] + current_direction[1], current_position[1] - current_direction[0])
        left_position = (current_position[0] - current_direction[1], current_position[1] + current_direction[0])

        # Check if the positions are valid and not in the grid
        valid_positions = [pos for pos in (forward_position, right_position, left_position) if pos in grid]

        if not valid_positions:
            return None

        # Choose the position that brings you closer to the goal
        closest_position = min(valid_positions, key=lambda pos: abs(pos[0] - goal[0]) + abs(pos[1] - goal[1]))

        # Update the path and current position
        path.append(closest_position)
        current_position = closest_position

        # Update the direction based on the movement
        if closest_position == forward_position:
            pass  # Keep the same direction (no need to change direction)
        elif closest_position == right_position:
            current_direction = (current_direction[1], -current_direction[0])  # Turn right
        elif closest_position == left_position:
            current_direction = (-current_direction[1], current_direction[0])  # Turn left

    return path

# Example usage:
grid = {(6, 18), (7, 17), (14, 13), (17, 12), (3, 13), (5, 19), (8, 18), (9, 17), (11, 14), (15, 14), (16, 13), (21, 9), (6, 20), (22, 10), (12, 18), (3, 15), (5, 21), (1, 17), (3, 17), (15, 18), (3, 19), (10, 15), (1, 21), (7, 16), (4, 11), (3, 21), (10, 17), (15, 13), (16, 12), (18, 18), (20, 12), (22, 9), (12, 17), (14, 14), (3, 14), (5, 11), (4, 13), (13, 18), (2, 15), (22, 11), (4, 15), (17, 18), (8, 15), (2, 17), (6, 17), (14, 18), (3, 18), (4, 17), (8, 17), (10, 14), (2, 19), (6, 10), (20, 9), (6, 19), (7, 18), (4, 19), (17, 13), (5, 20), (8, 19), (2, 21), (20, 11), (22, 8), (21, 10), (4, 12), (4, 21), (11, 17), (18, 13), (21, 12), (4, 14), (2, 16), (16, 18), (8, 16), (9, 15), (2, 18), (15, 12), (6, 9), (1, 22)}
start = (60, 18)
goal = (140, 13)
path = find_nearest_path(grid, start, goal)
print(path)