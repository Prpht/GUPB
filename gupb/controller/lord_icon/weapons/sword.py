from typing import List
from gupb.controller.lord_icon.distance import Point2d
from gupb.controller.lord_icon.weapons.weapon import Weapon


class Sword(Weapon):
    name = "sword"
    value = 3

    @staticmethod
    def get_attack_range(map, facing, position) -> List[Point2d]:
        forward_x, forward_y = facing.value[0], facing.value[1]
        return [
            (position[0] + forward_x, position[1] + forward_y),
            (position[0] + 2*forward_x, position[1] + 2*forward_y),
            (position[0] + 3*forward_x, position[1] + 3*forward_y)
        ]
