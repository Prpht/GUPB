import numpy as np
from gupb.model.characters import Action, Facing
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife, Axe, Bow, Sword, Amulet


POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]

weapons = {
    'knife': Knife,
    'axe': Axe,
    'bow_loaded': Bow,
    'bow_unloaded': Bow,
    'sword': Sword,
    'amulet': Amulet
}

weapons_onehot = {
    'knife': np.array([1, 0, 0, 0, 0]),
    'axe': np.array([0, 1, 0, 0, 0]),
    'bow_loaded': np.array([0, 0, 1, 0, 0]),
    'bow_unloaded': np.array([0, 0, 1, 0, 0]),
    'sword': np.array([0, 0, 0, 1, 0]),
    'amulet': np.array([0, 0, 0, 0, 1])
}

facing_onehot = {
    Facing.UP: np.array([1, 0, 0, 0]),
    Facing.RIGHT: np.array([0, 1, 0, 0]),
    Facing.DOWN: np.array([0, 0, 1, 0]),
    Facing.LEFT: np.array([0, 0, 0, 1]),
}

facings = {
    "U": ["L", "R"], "R": ["U", "D"], "D": ["R", "L"], "L": ["D", "U"]
}
forwards = {
    "U": np.array([-1, 0]), "R": np.array([0, 1]), "D": np.array([1, 0]), "L": np.array([0, -1])
}
facing_to_letter = {
    Facing.UP: "U",Facing.RIGHT: "R", Facing.DOWN: "D", Facing.LEFT: "L"
}
weapons_to_letter = {
    Knife: "K", Axe: "A", Bow: "B", Sword: "S", Amulet: "M"
}
weapons_name_to_letter = {
    'knife': "K", 'axe': "A", 'bow_loaded': "B", 'bow_unloaded': "B", 'sword': "S", 'amulet': "M"
}


def get_random_place_on_a_map(traversable: np.array) -> Coords:
    """
    I guess you have a good reason to get a random traversable place on a map.
    """
    for _ in range(50):  # Just to avoid while True lol
        rx = np.random.randint(traversable.shape[1])
        ry = np.random.randint(traversable.shape[0])
        if traversable[(ry, rx)]:
            return Coords(x=rx, y=ry)
