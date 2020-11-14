from __future__ import annotations
from dataclasses import dataclass
import logging
import os.path
import random
from typing import Dict, NamedTuple, Optional

import bresenham

from gupb.logger import core as logger_core
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import effects
from gupb.model import tiles
from gupb.model import weapons

verbose_logger = logging.getLogger('verbose')

TILE_ENCODING = {
    '=': tiles.Sea,
    '.': tiles.Land,
    '#': tiles.Wall,
}

WEAPON_ENCODING = {
    'K': weapons.Knife,
    'S': weapons.Sword,
    'A': weapons.Axe,
    'B': weapons.Bow,
    'M': weapons.Amulet,
}

Terrain = Dict[coordinates.Coords, tiles.Tile]


class ArenaDescription(NamedTuple):
    name: str
    menhir_position: coordinates.Coords


class Arena:
    def __init__(self, name: str, terrain: Terrain) -> None:
        self.name = name
        self.terrain: Terrain = terrain
        self.tiles_with_instant_effects: set[tiles.Tile] = set()
        self.size: tuple[int, int] = terrain_size(self.terrain)
        self.menhir_position: Optional[coordinates.Coords] = None
        self.mist_radius = int(self.size[0] * 2 ** 0.5) + 1

    @staticmethod
    def load(name: str) -> Arena:
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
        return Arena(name, terrain)

    def description(self) -> ArenaDescription:
        return ArenaDescription(self.name, self.menhir_position)

    def empty_coords(self) -> set[coordinates.Coords]:
        return set(coords for coords, tile in self.terrain.items() if tile.empty)

    def visible_coords(self, champion: characters.Champion) -> set[coordinates.Coords]:
        def estimate_border_point() -> tuple[coordinates.Coords, int]:
            if champion.facing == characters.Facing.UP:
                return coordinates.Coords(champion.position.x, 0), champion.position[1]
            elif champion.facing == characters.Facing.RIGHT:
                return coordinates.Coords(self.size[0] - 1, champion.position.y), self.size[0] - champion.position[0]
            elif champion.facing == characters.Facing.DOWN:
                return coordinates.Coords(champion.position.x, self.size[1] - 1), self.size[1] - champion.position.y
            elif champion.facing == characters.Facing.LEFT:
                return coordinates.Coords(0, champion.position.y), champion.position[0]

        border, distance = estimate_border_point()
        left = champion.facing.turn_left().value
        targets = [border + coordinates.Coords(i * left.x, i * left.y) for i in range(-distance, distance + 1)]
        visible = set()
        visible.add(champion.position)
        for coords in targets:
            ray = bresenham.bresenham(champion.position.x, champion.position.y, coords[0], coords[1])
            next(ray)
            for ray_coords in ray:
                if ray_coords not in self.terrain:
                    break
                visible.add(ray_coords)
                if not self.terrain[ray_coords].transparent:
                    break
        return visible

    def visible_tiles(self, champion: characters.Champion) -> dict[coordinates.Coords, tiles.TileDescription]:
        return {coords: self.terrain[coords].description() for coords in self.visible_coords(champion)}

    def step_forward(self, champion: characters.Champion) -> None:
        new_position = champion.position + champion.facing.value
        if self.terrain[new_position].passable:
            self.terrain[champion.position].leave(champion)
            champion.position = new_position
            self.terrain[champion.position].enter(champion)
            verbose_logger.debug(f"Champion {champion.controller.name} entered tile {new_position}.")
            ChampionEnteredTileReport(champion.controller.name, new_position).log(logging.DEBUG)

    def stay(self, champion: characters.Champion) -> None:
        self.terrain[champion.position].stay()

    def spawn_menhir(self, new_position: Optional[coordinates.Coords] = None) -> None:
        if self.menhir_position:
            self.terrain[self.menhir_position] = tiles.Land()
        new_position = random.sample(self.empty_coords(), 1)[0] if new_position is None else new_position
        self.menhir_position = new_position
        self.terrain[self.menhir_position] = tiles.Menhir()
        verbose_logger.debug(f"Menhir spawned at {self.menhir_position}.")
        MenhirSpawnedReport(self.menhir_position).log(logging.DEBUG)

    def increase_mist(self) -> None:
        self.mist_radius -= 1 if self.mist_radius > 0 else self.mist_radius
        if self.mist_radius:
            verbose_logger.debug(f"Radius of mist-free space decreased to {self.mist_radius}.")
            MistRadiusReducedReport(self.mist_radius).log(logging.DEBUG)
            for coords in self.terrain:
                distance = int(((coords.x - self.menhir_position.x) ** 2 +
                                (coords.y - self.menhir_position.y) ** 2) ** 0.5)
                if distance == self.mist_radius:
                    self.register_effect(effects.Mist(), coords)

    def register_effect(self, effect: effects.Effect, coords: coordinates.Coords) -> None:
        tile = self.terrain[coords]
        tile.effects.add(effect)
        if effect.lifetime() == effects.EffectLifetime.INSTANT:
            self.tiles_with_instant_effects.add(tile)

    def trigger_instants(self) -> None:
        for tile in self.tiles_with_instant_effects:
            tile.instant()
        self.tiles_with_instant_effects = set()


def terrain_size(terrain: Terrain) -> tuple[int, int]:
    estimated_x_size, estimated_y_size = max(terrain)
    return estimated_x_size + 1, estimated_y_size + 1


@dataclass(frozen=True)
class ChampionEnteredTileReport(logger_core.LoggingMixin):
    controller_name: str
    tile_coords: coordinates.Coords


@dataclass(frozen=True)
class MenhirSpawnedReport(logger_core.LoggingMixin):
    position: coordinates.Coords


@dataclass(frozen=True)
class MistRadiusReducedReport(logger_core.LoggingMixin):
    mist_radius: int
