from typing import List
from gupb.controller.lord_icon.distance import Point2d
from gupb.controller.lord_icon.weapons.weapon import Weapon


class Knife(Weapon):
    name = "knife"
    value = 1

    @staticmethod
    def get_attack_range(map, facing, position) -> List[Point2d]:
        value = facing.value
        return [(position[0] + value[0], position[1] + value[1])]
