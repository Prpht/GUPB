from gupb.model import characters
from gupb.model import coordinates
from typing import List, Dict, Optional

"""
    @ TODO:
        1) Load arena information into self.tuptable_map
        2) Process loaded arena to look for safe spaces and buildings (bigger chance for weapons)
        3) Store information about menhir position
        4) Add information about the mist

"""


class Map():
    def __init__(self, max_size: int = 75):
        self.tuptable_map: List[List[int]] = [[1]*max_size for _ in range(max_size)]
        self.weapons_position: Dict = {}
        self.menhir_position: Optional[coordinates.Coords]


    def decode_knowledge(self, knowledge: characters.ChampionKnowledge) -> None:
        for coord, tile in knowledge.visible_tiles.items():
            if tile.type == "land":
                self.tuptable_map[coord[0]][coord[1]] = 0
                if tile.loot and tile.loot.name != "knife":
                    self.weapons_position[tile.loot.name] = coord
