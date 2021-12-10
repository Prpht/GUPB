from gupb.model.characters import Facing
from gupb.model import coordinates


def bfs_shortest_path(graph, start, goal):
    """For given vertex return shortest path"""
    explored, queue = [], [[start]]
    while queue:
        path = queue.pop(0)
        node = path[-1]
        if node not in explored:
            neighbours = graph[node]
            for neighbour in neighbours:
                new_path = list(path)
                new_path.append(neighbour)
                queue.append(new_path)
                if neighbour == goal:
                    return new_path
            explored.append(node)


def move(controller, start, end):
    diff = end - start
    if start != end:
        if diff.x == 1:
            if controller.direction == Facing.RIGHT:
                # return True mean he should go forward
                return True
        elif diff.x == -1:
            if controller.direction == Facing.LEFT:
                return True
        elif diff.y == 1:
            if controller.direction == Facing.DOWN:
                return True
        elif diff.y == -1:
            if controller.direction == Facing.UP:
                return True
    return False


def move_all(controller, position):
    if position == coordinates.Coords(*controller.actual_path[0]):
        controller.actual_path.pop(0)
    actual_path_0 = coordinates.Coords(*controller.actual_path[0])
    if move(controller, position, actual_path_0):
        if len(controller.actual_path) == 1:
            controller.menhir_visited = True
            controller.move_to_chosen_place = False
        return True
    else:
        return False


def save_menhir_position_if_visible(controller, visible_coords):
    for v_coord in visible_coords:
        if visible_coords[v_coord].type == 'menhir':
            controller.menhir_position = v_coord
            break


def move_all_hide(controller, position):
    if position == coordinates.Coords(*controller.actual_path[0]):
        controller.actual_path.pop(0)
    actual_path_0 = coordinates.Coords(*controller.actual_path[0])
    if controller.move(position, actual_path_0):
        if len(controller.actual_path) == 1:
            controller.move_to_hide = False
            controller.camp_visited = True
            controller.turns = 2
            controller.only_attack = True
            controller.actual_path = []
        return True
    else:
        return False


def save_camp_position_if_visible(controller, visible_coords):
    for v_coord in visible_coords:
        if visible_coords[v_coord].type == 'land':
            place_next_to = (v_coord[0] + 0, v_coord[1] + 1)
            place_next_to2 = (v_coord[0] + 1, v_coord[1] + 0)
            place_next_to3 = (v_coord[0] + 0, v_coord[1] - 1)
            place_next_to4 = (v_coord[0] - 1, v_coord[1] + 0)
            def_place = 0
            for place in [place_next_to, place_next_to2, place_next_to3, place_next_to4]:
                try:
                    if controller.tiles_memory[place].type != 'land':
                        def_place += 1
                except KeyError as err:
                    pass
            if def_place == 3:
                controller.camp_position = v_coord
                break
