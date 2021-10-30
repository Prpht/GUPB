# source: https://gist.github.com/Nicholas-Swift/003e1932ef2804bebef2710527008f44

class Node:
    """A node class for A* Pathfinding"""

    def __init__(self, parent=None, position=None):
        self.parent = parent
        self.position = position

        self.g = 0
        self.h = 0
        self.f = 0

    def __eq__(self, other):
        return self.position == other.position

    def __lt__(self, other):
        return self.f < other.f


def astar(maze, start, end, passable_tiles=None):
    """Returns a list of tuples as a path from the given start to the given end in the given maze"""

    if passable_tiles is None:
        passable_tiles = ['land', 'menhir']

    # Create start and end node
    start_node = Node(None, start)
    start_node.g = start_node.h = start_node.f = 0
    end_node = Node(None, end)
    end_node.g = end_node.h = end_node.f = 0

    # Initialize both open and closed list
    open_list = []
    closed_list = []

    # Add the start node
    open_list.append(start_node)

    # Loop until you find the end
    while len(open_list) > 0:
        open_list.sort()

        # Pop current off open list, add to closed list
        current_node = open_list.pop(0)
        closed_list.append(current_node)

        # Found the goal
        if current_node == end_node:
            path = []
            current = current_node
            while current != start_node:
                path.append(current.position)
                current = current.parent
            return path[::-1]  # Return reversed path

        # Generate children
        for new_position in [(0, -1), (0, 1), (-1, 0), (1, 0)]:  # Adjacent squares

            # Get node position
            node_position = (current_node.position[0] + new_position[0], current_node.position[1] + new_position[1])

            # Make sure walkable terrain
            if maze.get(node_position) is None or maze[node_position].type not in passable_tiles:
                continue

            # Create new node
            child = Node(current_node, node_position)

            # Child is on the closed list
            if child in closed_list:
                continue

            # Create the f, g, and h values
            child.g = abs(child.position[0] - start_node.position[0]) + abs(
                child.position[1] - start_node.position[1])
            child.h = abs(child.position[0] - end_node.position[0]) + abs(
                child.position[1] - end_node.position[1])
            child.f = child.g + child.h

            # Child is already in the open list
            for open_node in open_list:
                if child == open_node and child.f > open_node.f:
                    continue

            # Add the child to the open list
            open_list.append(child)
