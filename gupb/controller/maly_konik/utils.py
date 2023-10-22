from gupb.model import characters

BEST_WEAPONS = {
    1: 'sword',
    2: 'axe',
    3: 'amulet',
    4: 'bow_unloaded',
    5: 'bow_loaded',
    6: 'knife',
}

ACTIONS = [
    characters.Action.ATTACK,
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.DO_NOTHING
]

CHAMPION_STARTING_HP: int = 8


def get_weapon_value(weapon_name: str) -> int:
    for value, weapon in BEST_WEAPONS.items():
        if weapon == weapon_name:
            return value

