import random

from gupb.model import coordinates, characters


POSSIBLE_ACTIONS: list[characters.Action] = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.ATTACK,
]


def manhattan_distance(pos_a: coordinates.Coords, pos_b: coordinates.Coords) -> int:
    return abs(pos_a.x - pos_b.x) + abs(pos_a.y - pos_b.y)
