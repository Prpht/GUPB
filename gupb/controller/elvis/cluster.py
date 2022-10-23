from typing import List, Tuple
import numpy as np

from gupb.model.coordinates import Coords
from gupb.model.tiles import TileDescription


class Cluster:
    def __init__(self, index):
        self.tiles: {Coords: TileDescription} = {}
        self.index: int = index
        self.neighbors: List[int] = []
        self.mini_neighbors: List[int] = []
        self.neighbor_distances: List[float] = []
        self.center_of_mass: Tuple[float, float] = (-1, -1)
        self.central_point: Coords = Coords(-1, -1)
        self.contains_menhir = False
        self.base_danger = 0.0
        self.extra_danger: {str: float} = {}
        self.danger_sum = 0.0

    def update_danger(self, no_enemies):
        if self.contains_menhir:
            self.base_danger = no_enemies / 2.0

        extra_danger_sum = 0.0
        for danger in self.extra_danger.values():
            extra_danger_sum += danger

        self.danger_sum = self.base_danger + extra_danger_sum

    def set_base_danger(self, no_enemies):
        if self.contains_menhir:
            self.base_danger = no_enemies / 2.0
        else:
            for tile in self.tiles.values():
                if tile.loot is not None and len(tile.loot) > 0:
                    self.base_danger = 3.0

        if len(self.neighbors) == 1:
            self.base_danger += 2.0
        else:
            self.base_danger += (len(self.neighbors) - 2)

    def get_distance_between_centers_of_mass(self, center: Tuple[float, float]):
        return np.sqrt(np.power(self.center_of_mass[0] - center[0],  2) + np.power(self.center_of_mass[1] - center[1], 2))

    def get_distance_from_center_of_mass(self, point: Coords):
        return np.sqrt(np.power(self.center_of_mass[0] - point.x, 2) + np.power(self.center_of_mass[1] - point.y, 2))

    def find_center_of_mass(self):
        x = 0
        y = 0
        count = 0
        for tile in self.tiles.keys():
            count += 1
            x += tile.x
            y += tile.y
            if self.tiles[tile].type == 'menhir':
                self.contains_menhir = True

        self.center_of_mass = (x / count, y / count)

    def find_central_point(self):
        self.find_center_of_mass()

        if Coords(int(round(self.center_of_mass[0])), int(round(self.center_of_mass[1]))) in self.tiles.keys():
            self.central_point = Coords(int(round(self.center_of_mass[0])), int(round(self.center_of_mass[1])))
        else:
            closest_point = None
            closest_distance = None
            for tile in self.tiles.keys():
                if closest_point is None or self.get_distance_from_center_of_mass(tile) < closest_distance:
                    closest_point = tile
                    closest_distance = self.get_distance_from_center_of_mass(tile)

            self.central_point = closest_point

