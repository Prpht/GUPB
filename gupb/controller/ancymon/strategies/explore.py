import random
from gupb.controller.ancymon.environment import Environment
from gupb.model import characters

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]
class Explore():
    def __init__(self, environment: Environment):
        self.environment: Environment = environment

    def decide(self) -> characters.Action:

        return random.choice(POSSIBLE_ACTIONS)

        # new_position = self.position + self.champion.facing.value
        # if self.collect_loot(new_position):
        #     return POSSIBLE_ACTIONS[2]
        # elif self.should_attack(new_position):
        #     return POSSIBLE_ACTIONS[3]
        # elif self.can_move_forward():
        #     return random.choices(
        #         population=POSSIBLE_ACTIONS[:3], weights=(5, 5, 90), k=1
        #     )[0]
        # else:

    # def can_move_forward(self):
    #     new_position = self.position + self.champion.facing.value
    #
    #     if self.is_mist(new_position):
    #         return False
    #     return (
    #         self.discovered_map[new_position].type == "land"
    #         and not self.discovered_map[new_position].character
    #     )
    #
    # def should_attack(self, new_position):
    #     if self.discovered_map[new_position].character:
    #         if (
    #             self.discovered_map[new_position].character.health
    #             <= self.discovered_map[self.position].character.health
    #         ):
    #             return True
    #         # opponent is not facing us
    #         elif (
    #             new_position + self.discovered_map[new_position].character.facing.value
    #             == self.position
    #         ):
    #             return False
    #
    #     return False
    #
    # def collect_loot(self, new_position):
    #     return (
    #         self.discovered_map[new_position].loot and self.weapon == Knife
    #     ) or self.discovered_map[new_position].consumable
    #
    # # freezes when stuck in mist
    # def is_mist(self, new_position):
    #     tile = self.discovered_map[new_position].effects
    #     if tile:
    #         effect = tile[0].type
    #         if effect == "mist":
    #             return True
    #     return False