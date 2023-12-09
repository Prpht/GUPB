from typing import Dict

from gupb.model import characters, tiles, coordinates
from gupb.model.weapons import Knife, Bow
from gupb.model.coordinates import Coords
class Environment():
    def __init__(self):
        self.old_health = 0
        self.flee_moves = 0
        self.map_known_len = -1
        self.enemies_left = -1
        self.enemies_num = -1
        self.poi = Coords(0, 0)
        self.discovered_map = dict()
        self.visible_map = dict()
        self.position: coordinates.Coords = None
        self.champion = None
        self.mist_seen = False
        self.menhir: coordinates.Coords = None
        self.weapon = Knife

    def update_environment(self, knowledge: characters.ChampionKnowledge):
        if self.champion is not None:
            self.old_health = self.champion.health
        self.position = knowledge.position
        self.enemies_left = knowledge.no_of_champions_alive
        self.enemies_num = max(self.enemies_num, self.enemies_left)
        self.champion = knowledge.visible_tiles[knowledge.position].character
        self.update_maps(knowledge.visible_tiles)
        self.weapon = self.champion.weapon

    def took_damage(self):
        return self.old_health > self.champion.health
    def manhatan_distance(self, node: Coords, goal:Coords):
        return abs(node.x - goal.x) + abs(node.y - goal.y)

    # def clear_far_maps_sector(self):
    #     for coords, description in self.discovered_map.items():
    #         coords = Coords(coords[0], coords[1])
    #         if self.manhatan_distance(self.position, coords) >= 10 and description.loot is not None:
    #             self.discovered_map.pop(coords)

    def update_maps(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        self.visible_map = dict()
        for coords, description in visible_tiles.items():
            self.visible_map[coords] = description
            self.discovered_map[coords] = description
            if self.mist_seen is False:
                for effect in description.effects:
                    if effect.type == 'mist':
                        self.mist_seen = True
            if self.menhir == None and self.discovered_map[coords].type == "menhir":
                self.menhir = coordinates.Coords(coords[0], coords[1])
            if self.map_known_len < max(coords[0], coords[1]):
                self.map_known_len = max(coords[0], coords[1])
