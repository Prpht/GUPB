from enum import Enum

import numpy as np

from gupb.model.tiles import Menhir, Wall, Sea, Land
from gupb.model.weapons import Knife, Sword, Bow, Axe, Amulet

FIELD_WEIGHT = 100

TILES = [Land, Sea, Wall, Menhir]

TILES_MAP = {tile().description().type: tile for tile in TILES}

WEAPONS = [(Knife, 100), (Sword, 25), (Bow, 1), (Axe, 10), (Amulet, 25)]
WEAPONS.sort(key=lambda x: x[1])

WEAPONS_MAP = {weapon().description(): weapon for weapon, _ in WEAPONS}

WEAPONS_ENCODING = {weapon().description(): value for weapon, value in WEAPONS}

FIELD_ATTACKED = FIELD_WEIGHT * FIELD_WEIGHT * 2

WEAPONS_PRIORITY = [weapon[0]().description() for weapon in WEAPONS]

# q_learning consts
LEARN = False


class StrategyAction(Enum):
    HIDE = 1,
    GO_TO_MENHIR = 2,


EPSILON = 0.1
LEARNING_RATE = 0.15
DISCOUNT_FACTOR = 0.9
REWARD_CONST = 10.0
PUNISHMENT_CONST = REWARD_CONST

DIST_PROPORTION_BINS = np.linspace(1, 6, num=6)
DIST_BINS = [1, 3, 5, 10, 25, 50]
MIST_BINS = [0, 1, 2, 3, 5, 10]

LEARNING_CHANGE_COUNT = 400
LEARNING_RATE_CHANGE = 0.05
DISCOUNT_FACTOR_CHANGE = 0.1

LEARNING_RATE_MIN = 0.1
DISCOUNT_FACTOR_MAX = 0.99
