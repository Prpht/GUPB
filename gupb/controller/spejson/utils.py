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

move_action_onehot = {
    None: np.array([0, 0, 0]),
    Action.TURN_LEFT: np.array([1, 0, 0]),
    Action.TURN_RIGHT: np.array([0, 1, 0]),
    Action.STEP_FORWARD: np.array([0, 0, 1]),
}

move_possible_action_onehot = {
    None: np.array([0, 0, 0, 0, 0]),
    Action.TURN_LEFT: np.array([1, 0, 0, 0, 0]),
    Action.TURN_RIGHT: np.array([0, 1, 0, 0, 0]),
    Action.STEP_FORWARD: np.array([0, 0, 1, 0, 0]),
    Action.ATTACK: np.array([0, 0, 0, 1, 0]),
    Action.DO_NOTHING: np.array([0, 0, 0, 0, 1]),
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


def padded_slice(arr, center, height, width, rad=6, fill=0):
    """
    Take a zero-padded slice of an array.
    """
    center = np.array(center)
    img_region = np.array([[0, height], [0, width]])
    slice_region = np.vstack([center - rad, center + rad + 1]).T

    pre_pad = np.abs(np.minimum(slice_region, 0))
    post_pad = np.abs(np.maximum(slice_region - img_region[:, 1], 0))

    slicing = np.vstack([np.maximum(slice_region[:, 0], 0), np.minimum(slice_region[:, 1], img_region[:, 1])]).T
    slicing = tuple(map(lambda x: slice(*x), slicing))
    padding = pre_pad + post_pad

    return np.pad(arr[slicing[0], slicing[1]], pad_width=padding, mode="constant", constant_values=fill)
