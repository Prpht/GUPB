from typing import Tuple, List
from gupb.model.characters import Action


def points_dist(cord1, cord2):
    return int(((cord1.x - cord2.x) ** 2 +
                (cord1.y - cord2.y) ** 2) ** 0.5)