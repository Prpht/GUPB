
from abc import abstractmethod
from typing import NamedTuple, List

from gupb.controller.lord_icon.distance import Point2d


class Weapon(NamedTuple):
    name: str
    value: int

    @staticmethod
    @abstractmethod
    def get_attack_range(map, facing, position) -> List[Point2d]:
        pass
