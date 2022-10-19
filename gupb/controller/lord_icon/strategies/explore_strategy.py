import random
from gupb.controller.lord_icon.distance import find_path
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.move import MoveController
from gupb.controller.lord_icon.strategies.core import Strategy
from gupb.model import characters
from gupb.model.characters import Action

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


class ExploreStrategy(Strategy):
    name = "ExploreStrategy"
    counter = 0

    @staticmethod
    def get_action(knowledge: Knowledge):
        sorted_weapons = dict(sorted(knowledge.weapons.items(), key=lambda item: item[1]))
        map = knowledge.map.copy()

        # Attack if you can
        for enemy in knowledge.enemies:
            if knowledge.character.can_attack(knowledge.map, enemy.position):
                return Action.ATTACK

        # Avoid attack range from enemies
        for enemy in knowledge.enemies:
            attack_range = enemy.predict_attack_range(map)
            for pos in attack_range:
                map[pos] = 1

        for weapon in sorted_weapons.keys():
            x, y = weapon[0], weapon[1]
            moves = find_path(map, knowledge.character.position, (x, y))
            if len(moves) > 0:
                return MoveController.next_move(knowledge, moves[0])
            else:
                continue

        return random.choice(POSSIBLE_ACTIONS)
