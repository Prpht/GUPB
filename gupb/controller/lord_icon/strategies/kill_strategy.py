import random
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


class KillerStrategy(Strategy):
    name = "KillerStrategy"
    counter = 0
    target = None

    @staticmethod
    def get_action(knowledge: Knowledge):

        def chase(enemy):
            x, y = (
                enemy.position[0],
                enemy.position[1],
            )
            moves = find_path(
                knowledge.map, knowledge.character.position, (x, y)
            )
            return moves

        if KillerStrategy.target and KillerStrategy.target in knowledge.enemies:
            for enemy in knowledge.enemies:
                if enemy == KillerStrategy.target:
                    KillerStrategy.target = enemy
        else:
            KillerStrategy.counter += 1

        if KillerStrategy.target and KillerStrategy.counter < 5:
            moves = chase(KillerStrategy.target)
            if moves:
                return MoveController.next_move(knowledge, moves[0])

        for enemy in sorted(
            knowledge.enemies,
            key=lambda x: (knowledge.character.distance(x)),
        ):
            moves = chase(enemy)
            if moves:
                KillerStrategy.target = enemy
                KillerStrategy.counter = 0
                return MoveController.next_move(knowledge, moves[0])

        return random.choice(POSSIBLE_ACTIONS)
