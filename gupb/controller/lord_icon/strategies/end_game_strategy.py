import numpy as np
from scipy import signal

from gupb.controller.lord_icon.distance import find_path, dist
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.move import MoveController
from gupb.controller.lord_icon.strategies.core import Strategy
from gupb.model import characters


class EndGameStrategy(Strategy):
    name = "EndGameStrategy"
    mist_points = []

    @staticmethod
    def get_action(knowledge: Knowledge):
        if knowledge.menhir:
            moves = find_path(knowledge.map, knowledge.character.position, knowledge.menhir)
            if moves:
                return MoveController.next_move(knowledge, moves[0])

        EndGameStrategy.mist_points = list(set(EndGameStrategy.mist_points + knowledge.mist_points))
        map_copy = knowledge.map.copy()

        for i in EndGameStrategy.mist_points:
            (x, y) = i
            map_copy[x, y] = 1

        safest_point = None
        safest_point_distance = 0
        n, m = map_copy.shape
        for i in range(n):
            for j in range(m):
                if map_copy[i][j] == 0:
                    distance_sum = sum([dist((i, j), cord) for cord in EndGameStrategy.mist_points])
                    if distance_sum > safest_point_distance:
                        safest_point = (i, j)
                        safest_point_distance = distance_sum

        if safest_point:
            moves = find_path(knowledge.map, knowledge.character.position, safest_point)
            if moves:
                return MoveController.next_move(knowledge, moves[0])
        # Just to be sure :)
        return characters.Action.TURN_LEFT
