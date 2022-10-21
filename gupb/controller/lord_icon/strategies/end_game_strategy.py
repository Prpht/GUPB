from gupb.controller.lord_icon.distance import find_path
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.move import MoveController
from gupb.controller.lord_icon.strategies.core import Strategy

from gupb.model.characters import Action


class EndGameStrategy(Strategy):
    name = "EndGameStrategy"
    enemies_ranges = []
    counter = 0

    @staticmethod
    def get_action(knowledge: Knowledge):
        map = knowledge.map.copy()

        # Avoid attack range from enemies
        for enemy in knowledge.enemies:
            attack_range = enemy.get_attack_range(map)
            for pos in attack_range:
                EndGameStrategy.enemies_ranges.append(pos)

        for enemy_range in EndGameStrategy.enemies_ranges:
            map[enemy_range] = 1

        if EndGameStrategy.counter == 2:
            EndGameStrategy.enemies_ranges = []
            EndGameStrategy.counter = 0

        EndGameStrategy.counter += 1

        if knowledge.menhir:
            moves = find_path(map, knowledge.character.position, knowledge.menhir)
            if len(moves) > 0:
                return MoveController.next_move(knowledge, moves[0])

        # Just to be sure :)
        return Action.TURN_LEFT
