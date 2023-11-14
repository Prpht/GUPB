from enum import Enum

class HUNTER_DECISION(Enum):
    LONG_RANGE_ATTACK = 1,
    ATTACK = 2,
    CHASE = 3,
    NO_ENEMY = 4

class ITEM_FINDER_DECISION(Enum):
    GO_FOR_POTION = 1,
    GO_FOR_LOOT = 2,
    NO_ITEMS = 3,
    ENEMY_ON_NEXT_MOVE = 4

class EXPLORER_DECISION(Enum):
    EXPLORE = 1,
    ENEMY_ON_NEXT_MOVE = 2