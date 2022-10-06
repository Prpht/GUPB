from gupb.model import characters


class KnowledgeDecoder:
    def __init__(self, knowledge: characters.ChampionKnowledge = None):
        self._knowledge = knowledge
        self._info = dict()
        self._map = None
        self.arena = None
        self.map_name = None

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
