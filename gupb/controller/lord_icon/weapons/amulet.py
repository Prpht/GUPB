from typing import List
from gupb.controller.lord_icon.distance import Point2d
from gupb.controller.lord_icon.weapons.weapon import Weapon


class Amulet(Weapon):
    name = "amulet"
    value = 5

    @staticmethod
    def get_attack_range(map, facing, position) -> List[Point2d]:
        x, y = position[0], position[1]
        attack_range = [(x + 1, y - 1), (x + 2, y - 2), (x - 1, y + 1), (x - 2, y + 2)]
        for i in range(-2, 3):
            if i != 0:
                attack_range.append((x + i, y + i))

        return attack_range
