from typing import Dict, Optional, List

import numpy as np
import math

from gupb.model import coordinates as cord
from gupb.model import characters
from gupb.model.arenas import ArenaDescription, Arena
from .utils import WORST_WEAPONS


class Mapa:
    def __init__(self) -> None:
        self.position: Optional[cord.Coords] = None
        self.menhir_position: Optional[cord.Coords] = None
        self.mist_position: List[cord.Coords] = []
        self.potion_position: Optional[cord.Coords] = None
        self.weapon_position: Optional[cord.Coords] = None
        self.weapon_name = None
        self.not_explored_terrain: Dict[cord.Coords] = {}

        self._enemies: List[cord.Coords] = []
        self.closest_enemy_cord = None
        self.enemy = None

        self.arena: Optional[Arena] = None
        self.grid_matrix: List[cord.Coords] = []

    def reset_map(self, arena_description: ArenaDescription) -> None:
        self.position = None
        self.weapon_position = None
        self.weapon_name = None
        self.menhir_position = None
        self.mist_position = []
        self.potion_position = None
        self.not_explored_terrain = {}
        self._enemies = []
        self.closest_enemy_cord = None
        self.enemy = None
        self.arena = Arena.load(arena_description.name)
        self.grid_matrix = np.ones((self.arena.size[0], self.arena.size[1]))

        for cords, tile in self.arena.terrain.items():
            if tile.description().type in ['wall', 'sea']:
                self.grid_matrix[cords.y, cords.x] = 0
            else:
                self.grid_matrix[cords.y, cords.x] = 1
                self.not_explored_terrain[cords] = 'NotExplored'

    def read_information(self, knowledge: characters.ChampionKnowledge, weapon_name) -> None:
        self.position = knowledge.position

        for coord, tile in knowledge.visible_tiles.items():
            # Widzimy broń
            if tile.loot and self.weapon_position is None:
                if WORST_WEAPONS[tile.loot.name] < WORST_WEAPONS[weapon_name]:
                    self.weapon_position = coord
                    self.weapon_name = tile.loot.name
            # Sprawdzamy czy nikt nie ukradł
            elif not tile.loot and self.weapon_position == coord:
                self.weapon_position = None
                self.weapon_name = None

            # Widzimy menhir
            if tile.type == 'menhir':
                self.menhir_position = coord

            # Widzimy mgle
            for effect in tile.effects:
                if effect.type == 'mist':
                    if math.sqrt((coord[0] - self.position[0]) ** 2 + (coord[1] - self.position[1]) ** 2) < 4:
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
            if tile.character and coord != self.position:
                self._enemies.append(coord)

        if self._enemies:
            self.closest_enemy_cord = min(self._enemies, key=lambda pos:
                                          math.sqrt(
                                              (pos[0] - self.position[0]) ** 2 + (pos[1] - self.position[1]) ** 2
                                          ))

            for coord, tile in knowledge.visible_tiles.items():
                if coord[0] == self.closest_enemy_cord[0] and coord[1] == self.closest_enemy_cord[1]:
                    self.enemy = tile.character

    def reset_enemies(self) -> None:
        self._enemies = []
        self.enemy = None
        self.closest_enemy_cord = None
