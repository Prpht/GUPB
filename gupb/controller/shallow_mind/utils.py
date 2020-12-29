from typing import Tuple, List
from gupb.model.characters import Action


def points_dist(cord1, cord2):
    return int(((cord1.x - cord2.x) ** 2 +
                (cord1.y - cord2.y) ** 2) ** 0.5)


def get_first_possible_move(moves: List[Tuple[Action, int]]):
    return next((next_move for next_move in moves if next_move[0] != Action.DO_NOTHING), (Action.DO_NOTHING, -1))
