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
    enemies_ranges = []
    counter = 0

    @staticmethod
    def get_action(knowledge: Knowledge):
        sorted_weapons = dict(sorted(knowledge.weapons.items(), key=lambda item: item[1]))
        map = knowledge.map.copy()

        # Avoid attack range from enemies
        for enemy in knowledge.enemies:
            attack_range = enemy.predict_attack_range(map)
            for pos in attack_range:
                ExploreStrategy.enemies_ranges.append(pos)

        for enemy_range in ExploreStrategy.enemies_ranges:
            map[enemy_range] = 1

        if ExploreStrategy.counter == 2:
            ExploreStrategy.enemies_ranges = []
            ExploreStrategy.counter = 0

        ExploreStrategy.counter += 1

        # Go to the nearest weapon
        for weapon in sorted_weapons.keys():
            x, y = weapon[0], weapon[1]
            moves = find_path(map, knowledge.character.position, (x, y))
            if len(moves) > 0:
                return MoveController.next_move(knowledge, moves[0])
            else:
                knowledge.weapons[weapon] = 1000

        # Just to be sure :)
        return random.choice(POSSIBLE_ACTIONS)
