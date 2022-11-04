import numpy as np
from gupb.model.characters import Action, Facing
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
