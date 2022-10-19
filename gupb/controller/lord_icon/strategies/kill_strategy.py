import random
from gupb.controller.lord_icon.distance import find_path
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.move import MoveController
from gupb.controller.lord_icon.weapons import ALL_WEAPONS
from gupb.controller.lord_icon.strategies.core import Strategy
from gupb.model import characters
from gupb.model.characters import Action

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


class KillStrategy(Strategy):
    name = "KillStrategy"
    counter = 0

    @staticmethod
    def get_action(knowledge: Knowledge):
        target = None

        # # Avoid attack range from enemies
        # map = knowledge.map.copy()
        # for enemy in knowledge.enemies:
        #     attack_range = enemy.predict_attack_range(map)
        #     for pos in attack_range:
        #         map[pos] = 1

        print('essa')

        for enemy in knowledge.enemies:
            if ALL_WEAPONS[enemy.weapon].value < ALL_WEAPONS[knowledge.character.weapon].value and enemy.health < knowledge.character.health:
                target = enemy

        print('essa1')

        if target and knowledge.character.can_attack(knowledge.map, target.position):
            return Action.ATTACK
        print('essa2')
        if target:
            x, y = target.position[0], target.position[1]
            moves = find_path(knowledge.map, knowledge.character.position, (x, y))
            if len(moves) > 0:
                return MoveController.next_move(knowledge, moves[0])
        print('essa3')
        # Attack if you can
        for enemy in knowledge.enemies:
            if knowledge.character.can_attack(knowledge.map, enemy.position):
                return Action.ATTACK
        print('essa4')
        return random.choice(POSSIBLE_ACTIONS)







