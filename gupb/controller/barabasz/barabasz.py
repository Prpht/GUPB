import random

from gupb import controller
from gupb.model import arenas, coordinates
from gupb.model import characters
from gupb.controller.barabasz.weapon_mechanics import deathzone

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
]


class SelfKnowledge:
    def __init__(self, knowledge: characters.ChampionKnowledge = None):
        self._knowledge = knowledge
        self._info = dict()

    def decode(self):
        tile = self.knowledge.visible_tiles.get(self.knowledge.position)
        character = tile.character if tile else None
        weapon = character.weapon.name if character else "knife"
        health = character.health
        facing = character.facing

        self._info['weapon'] = weapon
        self._info['health'] = health
        self._info['facing'] = facing

    @property
    def knowledge(self):
        return self._knowledge

    @knowledge.setter
    def knowledge(self, new_knowledge):
        self._knowledge = new_knowledge
        self.decode()


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BarabaszController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.knowledge_decoder = SelfKnowledge()

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
        
        if in_front in knowledge.visible_tiles.keys():
            if knowledge.visible_tiles[in_front].type == "wall" or knowledge.visible_tiles[in_front].type == "sea":
                return characters.Action.TURN_LEFT
            if self.knowledge_decoder._info['weapon']=='knife' and knowledge.visible_tiles[in_front].character:
                return characters.Action.ATTACK
            if self.knowledge_decoder._info['weapon']!='knife':
                if self.knowledge_decoder._info['weapon']=='bow_unloaded':
                    return characters.Action.ATTACK
                if self.knowledge_decoder._info['weapon']=='bow_loaded':
                    return random.choice([characters.Action.TURN_LEFT, 
                    characters.Action.TURN_RIGHT,
                    characters.Action.STEP_FORWARD, 
                    characters.Action.ATTACK])
                print("weapon: ", self.knowledge_decoder._info['weapon'], type(self.knowledge_decoder._info['weapon']))
                deathtiles = deathzone(weapon=self.knowledge_decoder._info['weapon'], 
                position=knowledge.position, 
                facing=self.knowledge_decoder._info['facing'].value)
                for cords in deathtiles:
                    if cords in knowledge.visible_tiles.keys() and knowledge.visible_tiles[cords].character:
                        print("SMACK! ", self.knowledge_decoder._info['weapon'])
                        print("Position: ", knowledge.position, "EnemyPos: ", cords)
                        return characters.Action.ATTACK

        weighted_random = random.choices(POSSIBLE_ACTIONS, weights=(1, 1, 3))[0]
        return weighted_random

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE
