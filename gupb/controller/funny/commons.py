from gupb.model.coordinates import Coords
from gupb.model import characters
import numpy as np

COORDS_ZERO = Coords(0, 0)


def r(x):
    return tuple(reversed(x))


def s(t1, t2):
    return t1[0] + t2[0], t1[1] + t2[1]


def d(t1, t2):
    return t1[0] - t2[0], t1[1] - t2[1]


def dist(c1, c2):
    return abs(c1[0] - c2[0]) + abs(c1[1] - c2[1])

