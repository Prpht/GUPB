from typing import Dict

from gupb.model import characters, tiles, coordinates
from gupb.model.weapons import Knife, Bow
class Environment():
    def __init__(self):
        self.map_known_len = -1
        self.enemies_left = -1
        self.discovered_map = dict()
        self.position: coordinates.Coords = None
        self.champion = None
        self.menhir: coordinates.Coords = None
        self.weapon = Knife

    def update_environment(self, knowledge: characters.ChampionKnowledge):
        self.position = knowledge.position
        self.enemies_left = knowledge.no_of_champions_alive
        self.champion = knowledge.visible_tiles[knowledge.position].character
        self.update_discovered_map(knowledge.visible_tiles)

    def update_discovered_map(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, description in visible_tiles.items():
            self.discovered_map[coords] = description
            if self.menhir == None and self.discovered_map[coords].type == "menhir":
                self.menhir = coordinates.Coords(coords[0], coords[1])
                # print(self.menhir)
            if self.map_known_len < max(coords[0], coords[1]):
                self.map_known_len = max(coords[0], coords[1])
