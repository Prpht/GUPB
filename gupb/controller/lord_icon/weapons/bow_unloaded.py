from typing import List
from gupb.controller.lord_icon.distance import Point2d
from gupb.controller.lord_icon.weapons.weapon import Weapon


class BowUnloaded(Weapon):
    name = "bow_unloaded"
    value = 5

    @staticmethod
    def get_attack_range(map, facing, position) -> List[Point2d]:
        return []
