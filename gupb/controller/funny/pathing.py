from gupb.controller.funny.commons import *

from queue import PriorityQueue
import numpy as np


def dijkstra(arr, start_pos, facing, danger_tiles=set()):
    y_max = len(arr)
    x_max = len(arr[0])

    facing = facing.value
    ans = np.full((y_max, x_max), 1 << 14, dtype=np.int16)
    parent = np.full((y_max, x_max, 2), -1)

    ans[r(start_pos)] = 0
    q = PriorityQueue()
    q.put((0, start_pos, facing))
    while not q.empty():
        val, pos, face = q.get()

        if val != ans[r(pos)]:
            continue

        for delta in characters.Facing:
            delta = delta.value
            new_pos = s(pos, delta)
            try:
                if arr[new_pos[1]][new_pos[0]] in ['#', '=']:
                    continue
            except IndexError:
                continue

            new_val = val
            if delta == face:
                new_val += 1
            elif delta + face == COORDS_ZERO:
                new_val += 3
            else:
                new_val += 2

            if new_pos in danger_tiles:
                new_val += 30

            if new_val < ans[r(new_pos)]:
                ans[r(new_pos)] = new_val
                parent[r(new_pos)] = pos
                q.put((new_val, new_pos, delta))

    return ans, parent


def create_path(pos, target, parent_map):
    path = []
    while target != pos:
        path.append(target)
        target = Coords(*parent_map[r(target)])

    return path


def get_next_move(pos, facing, next_pos):
    facing = facing.value
    direction = d(next_pos, pos)
    if direction == facing:
        return characters.Action.STEP_FORWARD
    elif facing[0] * direction[1] - facing[1] * direction[0] < 0:
        return characters.Action.TURN_LEFT
    else:
        return characters.Action.TURN_RIGHT