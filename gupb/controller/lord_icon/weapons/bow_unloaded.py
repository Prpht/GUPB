from typing import List
from gupb.controller.lord_icon.distance import Point2d
from gupb.controller.lord_icon.weapons.weapon import Weapon
from gupb.model.characters import Facing


class BowUnloaded(Weapon):
    name = "bow_unloaded"
    value = 5

    @staticmethod
    def get_attack_range(map, facing, position) -> List[Point2d]:
        n, m = map.shape
        x, y = position[0], position[1]
        attack_range = []
        if facing == Facing.UP:
            for i in range(y - 1, 0, -1):
                if map[x][i] == 10:
                    return attack_range
                attack_range.append((x, i))
        if facing == Facing.DOWN:
            for i in range(y + 1, m):
                if map[x][i] == 10:
                    return attack_range
                attack_range.append((x, i))
        if facing == Facing.LEFT:
            for i in range(x - 1, 0, -1):
                if map[i][y] == 10:
                    return attack_range
                attack_range.append((i, y))
        if facing == Facing.RIGHT:
            for i in range(x + 1, n):
                if map[i][y] == 10:
                    return attack_range
                attack_range.append((i, y))
        return attack_range
