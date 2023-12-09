from gupb.model import characters
from gupb.model import weapons
from gupb.model import coordinates as cord


WORST_WEAPONS = {
     'sword': 1,
     'axe': 3,
     'bow_loaded': 4,
     'bow_unloaded': 5,
     'amulet': 2,
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
    for weapon, value in WORST_WEAPONS.items():
        if weapon == weapon_name:
            return value


def get_cords_around_point(point_x: int, point_y: int):
    x, y = point_x, point_y

    distance = 1
    while True:
        for _ in range(distance):
            x += 1
            yield x, y

        for _ in range(distance):
            y += 1
            yield x, y

        distance += 1

        for _ in range(distance):
            x -= 1
            yield x, y

        for _ in range(distance):
            y -= 1
            yield x, y

        distance += 1


