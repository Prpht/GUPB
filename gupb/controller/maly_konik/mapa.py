from typing import Dict, Optional, List
from gupb.model import coordinates as cord
from gupb.model import characters
from gupb.model.arenas import ArenaDescription, Arena


class Mapa:
    def __init__(self) -> None:
        self.weapons_position: Dict = {}
        self.menhir_position: Optional[cord.Coords] = None
        self.mist_position: List[cord.Coords] = []
        self.potions_position: List[cord.Coords] = []
        self.not_explored_terrain: Dict[cord.Coords] = {}
        self.arena = None
        self.grid_matrix = None

    def reset_map(self, arena_description: ArenaDescription) -> None:
        self.arena = Arena.load(arena_description.name)
        self.weapons_position = {}
        self.menhir_position = None
        self.mist_position = []
        self.potions_position = []
        self.not_explored_terrain = {}

        self.grid_matrix = [[1 for _ in range(self.arena.size[0])] for _ in range(self.arena.size[1])]
        for cords, tile in self.arena.terrain.items():
            if tile.description().type in ['wall', 'sea']:
                self.grid_matrix[cords.y][cords.x] = 0
            else:
                self.grid_matrix[cords.y][cords.x] = 1
                self.not_explored_terrain[cords] = 'NotExplored'

    def read_information(self, knowledge: characters.ChampionKnowledge) -> None:
        for coord, tile in knowledge.visible_tiles.items():
            # Widzimy broń
            if tile.loot:
                self.weapons_position[tile.loot.name] = coord
            # Widzimy menhir
            if tile.type == 'menhir':
                self.menhir_position = coord
            # Widzimy mgle
            for effect in tile.effects:
                if effect.type == 'mist':
                    self.mist_position.append(coord)
                    break
            # Widzimy miksture
            if tile.consumable:
                self.potions_position.append(coord)
            # Pozycja zwiedzona, więc ją usuwamy
            if coord in self.not_explored_terrain:
                self.not_explored_terrain.pop(coord)
