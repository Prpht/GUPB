from gupb.model.coordinates import Coords
from gupb.model import characters, weapons
import numpy as np

COORDS_ZERO = Coords(0, 0)

WEAPON_CODING = {
    'knife': 'K',
    'sword': 'S',
    'axe': 'A',
    'bow_loaded': 'B',
    'bow_unloaded': 'B',
    'amulet': 'M'
}

# the bigger the better
WEAPON_PRIORITY = {
    'archipelago': {
        "B": 5,
        "A": 4,
        "S": 3,
        "K": 2,
        "M": 1
    },
    'fisher_island': {
        "A": 5,
        "B": 4,
        "S": 3,
        "K": 2,
        "M": 1
    },
    'dungeon': {
        "A": 5,
        "S": 4,
        "B": 3,
        "K": 2,
        "M": 1
    },
    'isolated_shrine': {
        "A": 5,
        "S": 4,
        "B": 3,
        "K": 2,
        "M": 1
    },
}

SAFE_POS = {
    'fisher_island': [
        Coords(9, 34),
        Coords(12, 15),
        Coords(30, 5),
        Coords(39, 10),
        Coords(30, 42),
        Coords(39, 26)
    ],
    'isolated_shrine': [
        Coords(6, 6),
        Coords(6, 12),
        Coords(12, 6),
        Coords(12, 12)
    ],
    'archipelago': [
        Coords(7, 6),
        Coords(24, 18),
        Coords(9, 30),
        Coords(9, 33),
        Coords(8, 32),
        Coords(32, 38),
        Coords(38, 20),
        Coords(38, 22),
        Coords(27, 20),
        Coords(31, 8),
        Coords(36, 8)
    ],
    'dungeon': [
        Coords(27, 24),
        Coords(22, 24),
        Coords(36, 21),
        Coords(48, 21),
        Coords(36, 37),
        Coords(36, 21),
        Coords(31, 16),
        Coords(18, 16),
        Coords(27, 14),
        Coords(14, 16),
        Coords(14, 9),
        Coords(14, 12),
        Coords(10, 12)
    ]
}


def r(x):
    return tuple(reversed(x))


def s(t1, t2):
    return t1[0] + t2[0], t1[1] + t2[1]


def d(t1, t2):
    return t1[0] - t2[0], t1[1] - t2[1]


def dist(c1, c2):
    return abs(c1[0] - c2[0]) + abs(c1[1] - c2[1])


# def quadrant(coords, arena_size):
#     x, y = coords
#     if y < arena_size[1] // 2:
#         if x > arena_size[1] // 2:
#             return 1
#         return 2
#     else:
#         if x > arena_size[1] // 2:
#             return 4
#         return 3
