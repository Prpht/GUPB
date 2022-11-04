import random

import numpy as np
from scipy import signal

from gupb.controller.lord_icon.distance import find_path
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.move import MoveController
from gupb.controller.lord_icon.strategies.core import Strategy
from gupb.model import characters

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


class RunStrategy(Strategy):
    name = "RunStrategy"

    @staticmethod
    def get_action(knowledge: Knowledge):

        map = knowledge.map.copy()

        def find_largest_area_center(map):
            kernel = -1.0 * np.ones((4, 4))
            conv = signal.convolve2d(map, kernel, mode="same")
            return np.unravel_index(np.argmax(conv), conv.shape)

        def get_move(map):
            point = find_largest_area_center(map)
            moves = find_path(map, knowledge.character.position, point)
            if moves:
                return moves[0]

        casual_move = get_move(map)

        for enemy in knowledge.enemies:
            for pos in enemy.get_attack_range(map):
                map[pos[0], pos[1]] = 1

        safe_move = get_move(map)

        for enemy in knowledge.enemies:
            for pos in enemy.predict_attack_range(map):
                map[pos[0], pos[1]] = 1

        safest_move = get_move(map)

        if safest_move:
            return MoveController.next_move(knowledge, safest_move)

        if safe_move:
            return MoveController.next_move(knowledge, safe_move)

        if casual_move:
            return MoveController.next_move(knowledge, casual_move)

        return random.choice(POSSIBLE_ACTIONS)
