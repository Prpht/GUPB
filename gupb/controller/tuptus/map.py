import numpy as np
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles
from gupb.model.arenas import Arena, ArenaDescription
from typing import List, Dict, Optional

"""
    @ TODO:
        1) Load arena information into self.tuptable_map
        2) Process loaded arena to look for safe spaces and buildings (bigger chance for weapons)
        3) Store information about menhir position
        4) Add information about the mist

"""


class Map():
    def __init__(self):
        self.tuptable_map: np.ndarray 
        self.weapons_position: Dict = {}
        self.menhir_position: Optional[coordinates.Coords]

    def decode_knowledge(self, knowledge: characters.ChampionKnowledge) -> None:
        for coord, tile in knowledge.visible_tiles.items():
            if tile.loot and tile.loot.name != "knife":
                self.weapons_position[tile.loot.name] = coord

    def _init_map(self, arena_description):
        self.tuptable_map = np.zeros(arena_description.size)
        for coords, tile in arena_description.terrain.items():
            if not tile.terrain_passable():
                self.tuptable_map[coords] = 1
