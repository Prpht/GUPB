from typing import Optional

import numpy as np
import scipy.ndimage

from gupb.controller.bupg.utils import weapon_class
from gupb.model import characters
from gupb.model.arenas import Terrain, terrain_size
from gupb.model.characters import ChampionDescription
from gupb.model.coordinates import Coords
from gupb.model.effects import EffectDescription, Fire, FIRE_DAMAGE


class MapKnowledge:
    def __init__(self, terrain: Terrain):
        self.terrain = terrain
        self.menhir_location: Optional[Coords] = None
        self.mnist_moved = False
        self._total_weight: float = 0
        self._mist_radius: int | None = None
        self._episode: int = 0
        self.looked_at = None
        self.opponents: dict[Coords, tuple[ChampionDescription, int]] = {}
        self.timestamp = 0
        W, H = terrain_size(terrain)
        self.danger_map = np.zeros(shape=(H, W), dtype=np.int8)

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

        self.trees = {
            coords: tile.description()
            for coords, tile in self.terrain.items()
            if tile.description().type == 'forest'
        }

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
        self.danger_map = np.zeros(shape=self.danger_map.shape, dtype=np.int8)

        for coords, tile in knowledge.visible_tiles.items():
            coords = Coords(*coords)
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

            if tile.character and tile.character.controller_name != "BUPG BUPG":
                for c, (o, t) in self.opponents.items():
                    if o.controller_name == tile.character.controller_name:
                        del self.opponents[c]
                        break
                self.opponents[coords] = (tile.character, self.timestamp)

        opponents_to_remove = []
        for coords, (opponent, t) in self.opponents.items():
            if self.timestamp - t > 3:
                opponents_to_remove.append(coords)

        for coords in opponents_to_remove:
            del self.opponents[coords]

        for c, (o, t) in self.opponents.items():
            wpn = weapon_class(o.weapon.name)
            danger_tiles = set(knowledge.visible_tiles) & set(
                wpn.cut_positions(self.terrain, Coords(*c), o.facing)
                ) & set(self.terrain)

            for x, y in danger_tiles:
                eff = wpn.cut_effect()
                self.danger_map[y, x] = eff.damage if not isinstance(eff, Fire) else FIRE_DAMAGE

        self.timestamp += 1

        for coords in self.mist:
            self.looked_at[coords.y, coords.x] = 0
            self.danger_map[coords.y, coords.x] += 1

        for coords in self.fires:
            self.danger_map[coords.y, coords.x] += FIRE_DAMAGE

    def get_most_unknown_point(self):
        distance_map = scipy.ndimage.distance_transform_edt(self.looked_at)
        arg = np.unravel_index(np.argmax(distance_map), shape=self.looked_at.shape)
        return arg[1], arg[0]

    def distance_to_mist(self, position: Coords):
        x, y = position
        min = float("inf")
        for w_x, w_y in self.mist:
            dist = abs(x - w_x) + abs(y - w_y)
            if dist < min:
                min = dist

        return min
