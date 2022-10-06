# THIS IS A MODIFIED VERSION OF random.py

import random

from gupb import controller
from gupb.model import arenas, coordinates
from gupb.model import characters

from gupb.controller.BenadrylowyBarabasz.knowledge_decoder import KnowledgeDecoder

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

WEIGHTED_ACTIONS = random.choices(POSSIBLE_ACTIONS, weights=(1,1,2,1), k=4)
print(WEIGHTED_ACTIONS)


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BarabaszController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.knowledge_decoder = KnowledgeDecoder()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BarabaszController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.knowledge_decoder.knowledge = knowledge

        # Check position, check which side one is facing, check tile description
        in_front = coordinates.add_coords(knowledge.position, self.knowledge_decoder._info['facing'].value)
        #print(knowledge.visible_tiles[in_front].type)
        if in_front in knowledge.visible_tiles.keys():
            #print("hurray!")
            if knowledge.visible_tiles[in_front].character:
                #print("Enemy")
                return characters.Action.ATTACK
            if knowledge.visible_tiles[in_front].type == "wall" or knowledge.visible_tiles[in_front].type == "sea":
                #print("obstacle", knowledge.visible_tiles[in_front].type)
                return characters.Action.TURN_LEFT

        return random.choice(WEIGHTED_ACTIONS)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return f'RandomController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE
