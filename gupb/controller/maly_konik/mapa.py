from typing import Dict, Optional, List

import numpy as np

from gupb.model import coordinates as cord
from gupb.model import characters
from gupb.model.arenas import ArenaDescription, Arena


class Mapa:
    def __init__(self) -> None:
        self.position: Optional[cord.Coords] = None
        self.weapons_position: Dict = {}
        self.menhir_position: Optional[cord.Coords] = None
        self.mist_position: List[cord.Coords] = []
        self.potion_position: Optional[cord.Coords] = None
        self.not_explored_terrain: Dict[cord.Coords] = {}
        # self.enemies: List[cord.Coords] = []
        self.arena: Optional[Arena] = None
        self.grid_matrix: List[cord.Coords] = []

    def reset_map(self, arena_description: ArenaDescription) -> None:
        self.position = None
        self.weapons_position = {}
        self.menhir_position = None
        self.mist_position = []
        self.potion_position = None
        self.not_explored_terrain = {}
        # self.enemies = []
        self.arena = Arena.load(arena_description.name)
        self.grid_matrix = np.ones((self.arena.size[0], self.arena.size[1]))

        for cords, tile in self.arena.terrain.items():
            if tile.description().type in ['wall', 'sea']:
                self.grid_matrix[cords.y, cords.x] = 0
            else:
                self.grid_matrix[cords.y, cords.x] = 1
                self.not_explored_terrain[cords] = 'NotExplored'

    def read_information(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position

        for coord, tile in knowledge.visible_tiles.items():
            # Widzimy broń
            if tile.loot:
                self.weapons_position[coord] = tile.loot.name
            elif coord in self.weapons_position:
                self.weapons_position.pop(coord)

            # Widzimy menhir
            if tile.type == 'menhir':
                self.menhir_position = coord

            # Widzimy mgle
            for effect in tile.effects:
                if effect.type == 'mist':
                    self.mist_position.append(coord)
                    break

            # Widzimy miksture
            if tile.consumable and self.potion_position is None:
                self.potion_position = coord
            # Sprawdzamy czy nikt nie ukradł miksturki
            elif not tile.consumable and self.potion_position == coord:
                self.potion_position = None

            # Pozycja zwiedzona, więc ją usuwamy
            if coord in self.not_explored_terrain:
                self.not_explored_terrain.pop(coord)

            # Widzimy wroga
            # if tile.character and coord != self.position:
            #     self.enemies.append(coord)

    # def reset_enemies(self) -> None:
    #     self.enemies = []
