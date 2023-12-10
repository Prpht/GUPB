from gupb.model import characters, consumables, effects
from gupb.model.coordinates import Coords
   
POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    ]

DIRECTIONS = [Coords(0, 1), Coords(0, -1), Coords(1, 0), Coords(-1, 0)]
