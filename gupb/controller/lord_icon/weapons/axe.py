from typing import List
from gupb.controller.lord_icon.distance import Point2d
from gupb.controller.lord_icon.weapons.weapon import Weapon
from gupb.model.characters import Facing


class Axe(Weapon):
    name = "axe"
    value = 3

    @staticmethod
    def get_attack_range(map, facing, position) -> List[Point2d]:
        value = facing.value
        forward_position_x = position[0] + value[0]
        forward_position_y = position[1] + value[1]
        if facing == Facing.UP or facing == Facing.DOWN:
            return [
                (forward_position_x, forward_position_y),
                (forward_position_x+1, forward_position_y),
                (forward_position_x-1, forward_position_y)
            ]
        if facing == Facing.LEFT or facing == Facing.RIGHT:
            return [
                (forward_position_x, forward_position_y),
                (forward_position_x, forward_position_y+1),
                (forward_position_x, forward_position_y-1)
            ]
