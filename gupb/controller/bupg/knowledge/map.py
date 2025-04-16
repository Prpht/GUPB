from typing import Optional

import numpy as np
import scipy.ndimage

from gupb.model import characters
from gupb.model.arenas import Terrain, terrain_size
from gupb.model.coordinates import Coords
from gupb.model.effects import EffectDescription
from gupb.model.games import MIST_TTH_PER_CHAMPION


class MapKnowledge:
    def __init__(self, terrain: Terrain):
        self.terrain = terrain
        self.menhir_location: Optional[Coords] = None
        self.mnist_moved = False
        self.estimated_menhir_location: np.ndarray | None = None
        self._total_weight: float = 0
        self._mist_radius: int | None = None
        self._episode: int = 0
        self.looked_at = None
        self.opponents: dict[Coords, int] = {}
        self.timestamp = 0

        # All these attributes MIGHT BE OUTDATED
        self.weapons = {
            coords: tile.loot.description()
            for coords, tile in self.terrain.items()
            if tile.loot
        }

        self.consumables = {
            coords: tile.consumable.description()
            for coords, tile in self.terrain.items()
            if tile.consumable
        }

        self.effects: dict[Coords, EffectDescription] = {}
        self.mist: set[Coords] = set()
        self.fires: set[Coords] = set()

    def remove_unreachable_weapons(self):
        weapons_to_remove = []
        for coords in self.weapons:
            if self.looked_at[coords.y, coords.x] == 0:
                weapons_to_remove.append(coords)

        for weapon in weapons_to_remove:
            del self.weapons[weapon]

    @property
    def mist_radius(self):
        if self._mist_radius is None:
            size = terrain_size(self.terrain)
            self._mist_radius = int(size[0] * 2 ** 0.5) + 1
        return self._mist_radius

    def update_terrain(self, knowledge: characters.ChampionKnowledge):
        self.looked_at[knowledge.position[1], knowledge.position[0]] = 0
        for coords, tile in knowledge.visible_tiles.items():
            self.looked_at[coords[1], coords[0]] = 0

            # Update weapons
            if coords in self.weapons and tile.loot is None:
                del self.weapons[coords]

            if tile.loot:
                self.weapons[coords] = tile.loot

            # Update consumables
            if coords in self.consumables and tile.consumable is None:
                del self.consumables[coords]

            if tile.consumable:
                self.consumables[coords] = tile.consumable

            # Update fires
            if "fire" in [ef.type for ef in tile.effects]:
                self.fires.add(coords)

            # Update mists
            if "mist" in [ef.type for ef in tile.effects]:
                self.mist.add(coords)

            if tile.type == "menhir":
                self.menhir_location = coords

            if tile.character:
                self.opponents[coords] = self.timestamp

        self.timestamp += 1


    def episode_tick(self):
        if self._mist_radius is None:
            size = terrain_size(self.terrain)
            self._mist_radius = int(size[0] * 2 ** 0.5) + 1

        self._episode += 1
        self.mnist_moved = self._episode % MIST_TTH_PER_CHAMPION == 0
        if self.mnist_moved:
            self._mist_radius -= 1

    def update_menhir_location(self, new_estimate: np.ndarray, weight: float = 1.0) -> None:
        if self.estimated_menhir_location is None:
            self.estimated_menhir_location = np.zeros((2,))
        self._total_weight += weight
        self.estimated_menhir_location += weight * (new_estimate - self.estimated_menhir_location) / self._total_weight

    def get_most_unknown_point(self):
        distance_map = scipy.ndimage.distance_transform_edt(self.looked_at)
        arg = np.unravel_index(np.argmax(distance_map), shape=self.looked_at.shape)
        return arg[1], arg[0]

    def find_closest_weapon(self, position: Coords, weapon_type: str):
        x, y = position
        min = float("inf")
        coords = None
        for (w_x, w_y), desc in self.weapons.items():
            if desc.name != weapon_type:
                continue

            dist = abs(x - w_x) + abs(y - w_y)
            if dist < min:
                min = dist
                coords = Coords(w_x, w_y)

        return coords

    def find_closest_tree(self, menhir_position: Coords):
        x, y = menhir_position
        min = float("inf")
        coords = None
        for (w_x, w_y), tile in self.terrain.items():
            if tile.description().type != 'forest':
                continue

            dist = abs(x - w_x) + abs(y - w_y)
            if dist < min:
                min = dist
                coords = Coords(w_x, w_y)

        return coords

    def distance_to_mist(self, position: Coords):
        x, y = position
        min = float("inf")
        for w_x, w_y in self.mist:
            dist = abs(x - w_x) + abs(y - w_y)
            if dist < min:
                min = dist

        return min

    def distance_to_potion(self, position: Coords):
        x, y = position
        min = float("inf")
        coords = None
        for w_x, w_y in self.consumables:
            dist = abs(x - w_x) + abs(y - w_y)
            if dist < min:
                min = dist
                coords = Coords(w_x, w_y)

        return min, coords