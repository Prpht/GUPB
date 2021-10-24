class Astar:
    @staticmethod
    def astar(grid, start_position, end_position, passable_tiles=['land', 'menhir']):
        start_node = Node(None, start_position)
        end_node = Node(None, end_position)

        open_list = []
        closed_list = []
        open_list.append(start_node)
        while len(open_list) > 0:
            open_list.sort()
            # Get the current node
            current_node = open_list.pop(0)
            # Pop current off open list, add to closed list
            closed_list.append(current_node)

            # Found the goal
            if current_node == end_node:
                path = []
                current = current_node  # parent, a nie current node, poniewaz nie mozemy wejsc ma mnehira
                while current != start_node:
                    path.append(current.position)
                    current = current.parent
                return path[::-1]

            # Generate children
            for new_position in [(0, -1), (0, 1), (-1, 0), (1, 0)]:  # Adjacent squares

                # Get node position
                node_position = (current_node.position[0] + new_position[0], current_node.position[1] + new_position[1])

                # # Make sure walkable terrain
                if grid.get(node_position) is None or grid[node_position].type not in passable_tiles:
                    continue

                # Create new node
                neighbor = Node(current_node, node_position)
                # Check if the neighbor is in the closed list
                if neighbor in closed_list:
                    continue
                # Generate heuristics (Manhattan distance)
                neighbor.g = abs(neighbor.position[0] - start_node.position[0]) + abs(
                    neighbor.position[1] - start_node.position[1])
                neighbor.h = abs(neighbor.position[0] - end_node.position[0]) + abs(
                    neighbor.position[1] - end_node.position[1])
                neighbor.f = neighbor.g + neighbor.h
                # Check if neighbor is in open list and if it has a lower f value
                if Astar.__add_to_open(open_list, neighbor):
                    # Everything is green, add neighbor to open list
                    open_list.append(neighbor)

    @staticmethod
    def __add_to_open(open_list, neighbor):
        for node in open_list:
            if neighbor == node and neighbor.f >= node.f:
                return False
        return True

class Node():
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