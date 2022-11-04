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
        self.mist_map: np.ndarray
        self.known_map: np.ndarray

    def decode_knowledge(self, knowledge: characters.ChampionKnowledge) -> None:
        for coord, tile in knowledge.visible_tiles.items():
            self.known_map[coord] = 1
            if tile.loot and tile.loot.name != "knife":
                self.weapons_position[tile.loot.name] = coord
            if tile.type == "menhir":
                self.menhir_position = coord
            #? Do i need 2 ifs? 
            if tile.effects:
                if tile.effects.type == "mist":
                    self.mist_map[coord] = 1


    def _init_map(self, arena_description):
        self.tuptable_map = np.zeros(arena_description.size)
        self.mist_map = np.zeros(arena_description.size)
        self.known_map = np.zeros(arena_description.size)
        for coords, tile in arena_description.terrain.items():
            if not tile.terrain_passable():
                self.tuptable_map[coords] = 1

    def quadron_exploration(self) -> np.ndarray:       
        height, width = self.known_map.shape

        q1 = self.known_map[:height//2, width//2:]
        q2 = self.known_map[:height//2, :width//2]
        q3 = self.known_map[height//2:, :width//2]
        q4 = self.known_map[height//2:, width//2:]

        q1_proc = np.sum(q1) / q1.size
        q2_proc = np.sum(q2) / q2.size
        q3_proc = np.sum(q3) / q3.size
        q4_proc = np.sum(q4) / q4.size


        return np.array([[q2_proc, q1_proc], [q3_proc, q4_proc]])


    @property
    def is_mist(self) -> bool:
        return any(self.mist_map)

