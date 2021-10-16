from enum import Enum

from gupb.model import characters
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords


class Direction(Enum):
    S = Coords(0, 1)
    W = Coords(-1, 0)
    N = Coords(0, -1)
    E = Coords(1, 0)


def get_direction(knowledge: ChampionKnowledge) -> Direction:
    for direction in Direction:
        if (knowledge.position + direction.value) in knowledge.visible_tiles:
            return direction


def get_distance(a: Coords, b: Coords) -> int:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** (1 / 2)


def left_walk(knowledge: ChampionKnowledge, direction: Direction) -> characters.Action:
    if knowledge.visible_tiles[knowledge.position + direction.value].type == 'land':
        return characters.Action.STEP_FORWARD
    else:
        return characters.Action.TURN_LEFT


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD
]