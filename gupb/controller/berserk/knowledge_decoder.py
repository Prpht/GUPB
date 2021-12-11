from gupb.model import characters
from gupb.model.coordinates import Coords
from gupb.model.arenas import Arena
from pathfinding.core.grid import Grid


class KnowledgeDecoder:
    def __init__(self, knowledge: characters.ChampionKnowledge = None):
        self._knowledge = knowledge
        self._info = dict()
        self._map = None
        self.arena = None
        self.map_name = None
        self._info['temp_safe_spot'] = None
        self._info['menhir_position'] = None
        self._info['map_size'] = None

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
        self._info['mist'] = self._look_for_mist()

        self._get_menhir_position()

    def _get_weapons_in_sight(self):
        return [Coords(*coords) for coords, tile in self.knowledge.visible_tiles.items()
                if tile.loot and coords != self.knowledge.position and tile.loot.name not in ["knife", "amulet", "bow"]]

    def _get_enemies_in_sight(self):
        return [Coords(*coords) for coords, tile in self.knowledge.visible_tiles.items()
                if tile.character and coords != self.knowledge.position]

    def _get_nearest_area(self, d=4):
        nearest_area = []
        for i in range(-d, d + 1):
            for j in range(-d, d + 1):
                nearest_area.append(self.knowledge.position + Coords(i, j))

        return [point for point in nearest_area if point in self.knowledge.visible_tiles.keys()]

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

    @property
    def info(self):
        return self._info

    @property
    def map(self):
        return self._map

    @map.setter
    def map(self, new_map: Arena):
        self._map = new_map

    def _get_menhir_position(self):
        if self.info['menhir_position'] is None:
            for coords, tile in self.knowledge.visible_tiles.items():
                if tile.type == 'menhir':
                    self.info['menhir_position'] = Coords(*coords)

    def load_map(self, map_name):
        self.map_name = map_name
        arena = Arena.load(map_name)
        self.arena = arena
        map_matrix = [[1 for x in range(arena.size[0])] for y in range(arena.size[1])]
        self._info['map_size'] = (arena.size[0], arena.size[1])
        self._info['temp_safe_spot'] = Coords(round(arena.size[0]/2), round(arena.size[1]/2))
        for cords, tile in arena.terrain.items():
            map_matrix[cords.y][cords.x] = 0 if tile.description().type in ['wall', 'sea'] else 1
            if tile.description().loot:
                map_matrix[cords.x][cords.y] = 0 if tile.description().loot.name in ["knife", "amulet", "bow"] else 1
        return map_matrix

    def reset(self, knowledge: characters.ChampionKnowledge = None):
        self._knowledge = knowledge
        self._info = dict()
        self._map = None
        self.arena = None
        self._info['temp_safe_spot'] = None
        self._info['menhir_position'] = None
        self._info['map_size'] = None
