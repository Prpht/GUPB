from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model.coordinates import Coords, add_coords


class Node:
    def __init__(self, coords: Coords, facing:  Facing):
        self.coords:  Coords = coords
        self.orientation:  Facing = facing
        self.connections = dict()


def build_graph(knowledge):
    graph = dict()
    coords = set()
    for coord, tile_desc in knowledge.visible_tiles.items():
        if tile_desc.type == "land" or tile_desc.type == "menhir":
            coords.add(coord)
            for direction in Facing:
                graph[(coord, direction)] = Node(coord, direction)

    for key, node in graph.items():
        coord, facing = key
        if (add_coords(coord,facing.value), facing) in graph:
            node.connections[graph[(add_coords(coord,facing.value),facing)]] = characters.Action.STEP_FORWARD

    for direction in Facing:
        for coord in coords:
            graph[(coord,direction)].connections[graph[(coord,direction.turn_right())]] = characters.Action.TURN_RIGHT
            graph[(coord,direction)].connections[graph[(coord,direction.turn_left())]] = characters.Action.TURN_LEFT
    # print(len(list(graph.keys())))
    return graph

def get_reachable(start):
    queue = [start]
    already_visited = set()
    while queue:
        curr = queue.pop()
        already_visited.add(curr)
        for neighbour in curr.connections.keys():
            if neighbour not in already_visited:
                queue.append(neighbour)
    return {v.coords for v in already_visited}


def find_shortest_path(start, end=None):

    queue = [start]
    already_visited = set()
    shortest_paths = {
        start: []
    }
    while queue:
        curr = queue.pop(0)
        # print(curr)
        if curr.coords == end and end is not None:
            return shortest_paths[curr]
        already_visited.add(curr)
        for neighbour in curr.connections.keys():
            if neighbour not in already_visited:
                queue.append(neighbour)
                shortest_paths[neighbour] = shortest_paths[curr]+[neighbour]
                already_visited.add(neighbour)

    if end is None:
        return shortest_paths

    return None

def find_closest_orientation(shortest_paths, graph, coord):
    closest_orientation, best_length = None, 10000000
    for orientation in Facing:
        length = len(shortest_paths[graph[(coord,orientation)]])
        if length<best_length:
            closest_orientation = orientation
            best_length = length
    return closest_orientation, best_length

