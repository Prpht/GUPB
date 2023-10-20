import os
from typing import Dict, NamedTuple, Optional

from gupb.model import arenas, tiles, coordinates, weapons
from gupb.model import characters



class Memory:
    def __init__(self):
        self.position: coordinates.Coords = None
        no_of_champions_alive: int = 0
        self.map: Map = None
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.position: coordinates.Coords = None
        no_of_champions_alive: int = 0
        self.map = Map.load(arena_description.name)
    
    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position
        self.no_of_champions_alive = knowledge.no_of_champions_alive

class Map:
    def __init__(self, name: str, terrain: arenas.Terrain) -> None:
        self.name = name
        self.terrain: arenas.Terrain = terrain
        self.size: tuple[int, int] = arenas.terrain_size(self.terrain)
        self.menhir_position: Optional[coordinates.Coords] = None
        self.mist_radius = int(self.size[0] * 2 ** 0.5) + 1

    @staticmethod
    def load(name: str) -> arenas.Arena:
        terrain = dict()
        arena_file_path = os.path.join('resources', 'arenas', f'{name}.gupb')
        with open(arena_file_path) as file:
            for y, line in enumerate(file.readlines()):
                for x, character in enumerate(line):
                    if character != '\n':
                        position = coordinates.Coords(x, y)
                        if character in arenas.TILE_ENCODING:
                            terrain[position] = arenas.TILE_ENCODING[character]()
                        elif character in arenas.WEAPON_ENCODING:
                            terrain[position] = tiles.Land()
                            terrain[position].loot = arenas.WEAPON_ENCODING[character]()
        return arenas.Arena(name, terrain)
