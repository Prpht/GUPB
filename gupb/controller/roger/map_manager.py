import os

from typing import Dict, Optional, List, Tuple, Callable
from math import inf

from gupb.controller.roger.constans_and_types import SeenWeapon, EpochNr, T, SeenEnemy
from gupb.controller.roger.utils import get_distance
from gupb.model import coordinates, tiles
from gupb.model.arenas import Terrain, TILE_ENCODING, WEAPON_ENCODING
from gupb.model.characters import ChampionDescription
from gupb.model.coordinates import Coords


class MapManager:
    def __init__(self):
        self.seen_tiles: Dict[coordinates.Coords, Tuple[tiles.TileDescription, int]] = {}
        self.terrain: Optional[Terrain] = None
        self.arena_size = (50, 50)
        self.menhir_coords: Optional[coordinates.Coords] = None
        self.weapons_coords: Dict[coordinates.Coords, SeenWeapon] = {}
        self.potions_coords: Dict[coordinates.Coords, EpochNr] = {}
        self.enemies_coords: Dict[coordinates.Coords, SeenEnemy] = {}
        self.mist_coords: List[coordinates.Coords] = []
        self.current_position: Optional[coordinates.Coords] = None
        self.epoch: EpochNr = 0

    def reset(self, arena_name: str):
        self.seen_tiles = {}
        self.menhir_coords = None
        self.weapons_coords = {}
        self.load_arena(arena_name)
        self.potions_coords = {}
        self.mist_coords = []

    def update(self, current_position: coordinates.Coords, epoch_nr: EpochNr,
               tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        self.current_position = current_position
        self.epoch = epoch_nr
        self.seen_tiles.update(dict((x[0], (x[1], self.epoch)) for x in tiles.items()))
        self.look_for_important_items(tiles)

    def look_for_important_items(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, tile in tiles.items():
            self.check_menhir(coords, tile)
            self.check_potion(coords, tile)
            self.check_weapon(coords, tile)
            self.check_mist(coords, tile)

    def check_menhir(self, coords: coordinates.Coords, tile: tiles.TileDescription):
        if not self.menhir_coords:
            if tile.type == 'menhir':
                self.menhir_coords = coords

    def check_potion(self, coords: coordinates.Coords, tile: tiles.TileDescription):
        if tile.consumable:
            if tile.consumable.name == 'potion':
                self.potions_coords[coords] = self.epoch
        else:
            self.potions_coords.pop(coords, None)

    def check_weapon(self, coords: coordinates.Coords, tile: tiles.TileDescription):
        if self.weapons_coords.get(coords):
            self._update_weapon(coords, tile)
        if tile.loot:
            self._add_weapon(coords, tile)

    def check_mist(self, coords: coordinates.Coords, tile: tiles.TileDescription):
        for effect in tile.effects:
            if effect.type == 'mist':
                self.mist_coords.append(coords)

    def check_enemy(self, coords: coordinates.Coords, tile: tiles.TileDescription):
        if tile.character:
            if coords != self.current_position:
                self.enemies_coords[coords] = SeenEnemy(tile.character, self.epoch)
        else:
            self.enemies_coords.pop(coords, None)

    def find_nearest_mist_coords(self) -> Optional[coordinates.Coords]:
        min_distance_squared = 2 * self.arena_size[0] ** 2
        nearest_mist_coords = None
        for coords in self.mist_coords:
            distance_squared = (coords.x - self.current_position.x) ** 2 + (coords.y - self.current_position.y) ** 2
            if distance_squared < min_distance_squared:
                min_distance_squared = distance_squared
                nearest_mist_coords = coords
        return nearest_mist_coords

    def load_arena(self, name: str):
        terrain = dict()
        arena_file_path = os.path.join('resources', 'arenas', f'{name}.gupb')
        with open(arena_file_path) as file:
            for y, line in enumerate(file.readlines()):
                for x, character in enumerate(line):
                    if character != '\n':
                        position = coordinates.Coords(x, y)
                        if character in TILE_ENCODING:
                            terrain[position] = TILE_ENCODING[character]()
                        elif character in WEAPON_ENCODING:
                            terrain[position] = tiles.Land()
                            terrain[position].loot = WEAPON_ENCODING[character]()
        self.terrain = terrain
        x_size, y_size = max(terrain)
        self.arena_size = (x_size+1, y_size+1)

    def _add_weapon(self, coords, tile):
        self.weapons_coords[coords] = SeenWeapon(tile.loot.name, self.epoch)

    def _update_weapon(self, coords, tile):
        if not tile.loot:
            del self.weapons_coords[coords]

    def get_nearest_potion_coords(self) -> Optional[Coords]:
        if self.potions_coords:
            coords, _ = self.get_nearest(self.current_position, self.potions_coords)
            return coords
        else:
            return None

    def get_nearest(self, position: Coords,  items: Dict[Coords, T], metric: Callable = get_distance) -> Tuple[Coords, T]:
        nearest_coords = None
        nearest_distance = inf
        for coords in items:
            distance = metric(position, coords)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_coords = coords
        return nearest_coords, items[nearest_coords]

    def get_4_tiles_around(self):
        tiles = []
        tiles.append(self.current_position + Coords(0, 1))
        tiles.append(self.current_position + Coords(0, -1))
        tiles.append(self.current_position + Coords(1, 0))
        tiles.append(self.current_position + Coords(-1, 0))
        return tiles

