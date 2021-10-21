from gupb.model import characters
from gupb.model.coordinates import Coords


class KnowledgeDecoder:
    def __init__(self, knowledge: characters.ChampionKnowledge = None):
        self._knowledge = knowledge
        self._info = {}

    def decode(self):
        tile = self.knowledge.visible_tiles.get(self.knowledge.position)
        character = tile.character if tile else None
        weapon = character.weapon.name if character else "knife"
        health = character.health
        facing = character.facing

        self._info['weapon'] = weapon
        self._info['health'] = health
        self._info['facing'] = facing
        self._info['enemies_in_sight'] = self._get_enemies_in_sight()
        self._info['weapons_in_sight'] = self._get_weapons_in_sight()

    def _get_weapons_in_sight(self):
        return [Coords(*coords) for coords, tile in self.knowledge.visible_tiles.items()
                if tile.loot and coords != self.knowledge.position and tile.loot.name != "knife"]

    def _get_enemies_in_sight(self):
        return [Coords(*coords) for coords, tile in self.knowledge.visible_tiles.items()
                if tile.character and coords != self.knowledge.position]

    def _get_nearest_area(self):
        x, y = self._knowledge.position

        nearest_area = [Coords(x + 1, y),
                        Coords(x, y + 1),
                        Coords(x - 1, y),
                        Coords(x, y + 1),
                        Coords(x + 1, y + 1),
                        Coords(x + 1, y - 1),
                        Coords(x - 1, y + 1),
                        Coords(x - 1, y - 1)]
        return nearest_area

    def _look_for_mist(self):
        visible_tiles = self.knowledge.visible_tiles
        mist_coords = []
        for coord in self._get_nearest_area():
            tile = visible_tiles[coord]
            for effect in tile.effects:
                if effect.type == 'mist':
                    mist_coords.append(coord)
        return mist_coords

    @property
    def knowledge(self):
        return self._knowledge

    @knowledge.setter
    def knowledge(self, new_knowledge):
        self._knowledge = new_knowledge
        self.decode()
