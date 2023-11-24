from gupb.model import characters
from gupb.model import weapons


BEST_WEAPONS = {
     'sword': 1,
     'axe': 2,
     'bow_loaded': 3,
     'bow_unloaded': 4,
     'amulet': 5,
     'knife': 6,
}

WEAPONS = {
    "bow_unloaded": weapons.Bow(),
    "bow_loaded": weapons.Bow(),
    "axe": weapons.Axe(),
    "sword": weapons.Sword(),
    "knife": weapons.Knife(),
    "amulet": weapons.Amulet()
}

ACTIONS = [
    characters.Action.ATTACK,
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.DO_NOTHING,
    characters.Action.STEP_BACKWARD
]

CHAMPION_STARTING_HP: int = 8


def get_weapon_value(weapon_name: str) -> int:
    for value, weapon in BEST_WEAPONS.items():
        if weapon == weapon_name:
            return value
