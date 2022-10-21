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
    target = None

    @staticmethod
    def get_action(knowledge: Knowledge):


        # # Avoid attack range from enemies
        # map = knowledge.map.copy()
        # for enemy in knowledge.enemies:
        #     attack_range = enemy.predict_attack_range(map)
        #     for pos in attack_range:
        #         map[pos] = 1

        # Attack if you can
        for enemy in knowledge.enemies:
            if knowledge.character.can_attack(knowledge.map, enemy.position):
                return Action.ATTACK

        if KillStrategy.target is None:
            for enemy in knowledge.enemies:
                if ALL_WEAPONS[enemy.weapon].value < ALL_WEAPONS[
                    knowledge.character.weapon].value and enemy.health <= knowledge.character.health:
                    KillStrategy.target = enemy

        if KillStrategy.target and knowledge.character.can_attack(knowledge.map, KillStrategy.target.position):
            return Action.ATTACK

        if KillStrategy.target:
            x, y = KillStrategy.target.position[0], KillStrategy.target.position[1]
            moves = find_path(knowledge.map, knowledge.character.position, (x, y))
            if len(moves) > 0:
                return MoveController.next_move(knowledge, moves[0])

        # Attack if you can
        for enemy in knowledge.enemies:
            if knowledge.character.can_attack(knowledge.map, enemy.position):
                return Action.ATTACK

        return random.choice(POSSIBLE_ACTIONS)
