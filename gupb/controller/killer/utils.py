from enum import Enum
from numpy import ndarray, shape

# Available directions
_DIR = [[0, 1], [0, -1], [1, 0], [-1, 0]]


# Land descriptions
class PathConstants(Enum):
    WALL = 0
    WALKABLE = 1


def find_path(arr: ndarray,
              visited: ndarray,
              curr_pos: tuple,
              path: list,
              min_sought_val: int = 2
              ) -> bool:
    x_bound, y_bound = shape(arr)

    visited[curr_pos[0]][curr_pos[1]] = 1
    if arr[curr_pos[0]][curr_pos[1]] == PathConstants.WALL.value:
        return False

    path.append(curr_pos)
    if arr[curr_pos[0]][curr_pos[1]] >= min_sought_val:
        return True

    for i in range(4):
        x = curr_pos[0] + _DIR[i][0]
        y = curr_pos[1] + _DIR[i][1]

        if (x >= 0 and y >= 0) and \
           (x < x_bound and y < y_bound) and \
           (not visited[x][y]):
            if find_path(arr, visited, (x, y), path, min_sought_val):
                return True

    path.pop()
    return False

