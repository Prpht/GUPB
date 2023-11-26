from enum import Enum
from typing import NamedTuple, NewType, TypeVar

from gupb.model import characters, tiles
from gupb.model.characters import ChampionDescription


class WeaponValue(Enum):
    KNIFE           = 1
    BOW_UNLOADED    = 2
    BOW_LOADED      = 3
    AMULET          = 4
    AXE             = 5
    SWORD           = 6


class States(Enum):
    RANDOM_WALK     = 1
    HEAD_TO_WEAPON  = 2
    HEAD_TO_MENHIR  = 3
    FINAL_DEFENCE   = 4
    HEAD_TO_CENTER  = 5
    HEAD_TO_POTION  = 6


EpochNr = NewType("EpochNr", int)
T = TypeVar("T")


class SeenWeapon(NamedTuple):
    name: str
    seen_epoch_nr: EpochNr


class SeenEnemy(NamedTuple):
    enemy: ChampionDescription
    seen_epoch_nr: EpochNr


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.ATTACK,
    characters.Action.DO_NOTHING
]

