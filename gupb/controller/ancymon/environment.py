from typing import Dict

from gupb.model import characters, tiles, coordinates
from gupb.model.weapons import Knife, Bow
class Environment():
    def __init__(self):
        self.map_known_len = -1
        self.enemies_left = -1
        self.enemies_num = -1
        self.discovered_map = dict()
        self.visible_map = dict()
        self.position: coordinates.Coords = None
        self.champion = None
        self.menhir: coordinates.Coords = None
        self.weapon = Knife

    def update_environment(self, knowledge: characters.ChampionKnowledge):
        self.position = knowledge.position
        self.enemies_left = knowledge.no_of_champions_alive
        self.enemies_num = max(self.enemies_num, self.enemies_left)
        self.champion = knowledge.visible_tiles[knowledge.position].character
        self.update_maps(knowledge.visible_tiles)
        self.weapon = self.champion.weapon

    def update_maps(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        self.visible_map = dict()
        for coords, description in visible_tiles.items():
            self.visible_map[coords] = description
            self.discovered_map[coords] = description
            if self.menhir == None and self.discovered_map[coords].type == "menhir":
                self.menhir = coordinates.Coords(coords[0], coords[1])
            if self.map_known_len < max(coords[0], coords[1]):
                self.map_known_len = max(coords[0], coords[1])
