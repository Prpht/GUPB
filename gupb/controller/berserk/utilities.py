import numpy as np
from gupb.model.coordinates import Coords


def distance(point1, point2) -> int:
    # if isinstance(point1, Coords) and isinstance(point2, Coords):
    #     return abs(point1.x - point2.x) + abs(point1.y - point2.y)
    # else:
    return abs(point1[0] - point2[0]) + abs(point1[1] - point2[1])


def epsilon_desc(episode):
    if episode <= 20:
        return 1
    else:
        return 0.2
