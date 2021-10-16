from gupb.model import characters
from gupb.model.coordinates import Coords


class KnowledgeDecoder:
    def __init__(self, knowledge: characters.ChampionKnowledge = None):
        self._knowledge = knowledge

    def decode(self):
        coords = self.knowledge.position
        tile = self.knowledge.visible_tiles.get(coords)
        character = tile.character if tile else None
        weapon = character.weapon.name if character else "knife"

        enemies_in_sight = [Coords(*coords) for coords, tile in self.knowledge.visible_tiles.items()
                            if tile.character and coords != self.knowledge.position]
        return enemies_in_sight, coords, tile, character, weapon,

    @property
    def knowledge(self):
        return self._knowledge

    @knowledge.setter
    def knowledge(self, new_knowledge):
        self._knowledge = new_knowledge
