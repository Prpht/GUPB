from typing import Optional

import numpy as np

from gupb.model import arenas, tiles, characters, weapons, coordinates, consumables
from gupb.controller.batman.utils.copyable import Copyable


def manhattan_distance(start: coordinates.Coords, end: coordinates.Coords) -> int:
    return abs(start.x - end.x) + abs(start.y - end.y)


class TileKnowledge(Copyable):
    def __init__(self, coords: coordinates.Coords):
        self.coords = coords
        self.type: Optional[str] = None
        self.last_seen: Optional[int] = -1
        self.weapon: Optional[weapons.WeaponDescription] = None
        self.character: Optional[characters.ChampionDescription] = None
        self.consumable: Optional[consumables.ConsumableDescription] = None

        # effects (are there any other?)
        self.mist: bool = False
        self.attacked: bool = False

    @property
    def passable(self) -> bool:
        return self.type not in ("wall", "sea")

    def update(self, tile: tiles.TileDescription, episode: int) -> None:
        self.last_seen = episode
        self.type = tile.type
        self.weapon = tile.loot
        self.character = tile.character
        self.consumable = tile.consumable

        self.mist = any([effect.type == "mist" for effect in tile.effects])
        self.attacked = any([effect.type == "weaponcut" for effect in tile.effects])


class ChampionKnowledge(Copyable):
    def __init__(
        self,
        champion_description: characters.ChampionDescription,
        position: coordinates.Coords,
    ) -> None:
        self.name = champion_description.controller_name
        self.position = position
        self.health = champion_description.health
        self.weapon = champion_description.weapon.name
        self.facing = champion_description.facing


class WeaponKnowledge(Copyable):
    def __init__(
        self,
        weapon_description: weapons.WeaponDescription,
        position: coordinates.Coords,
    ) -> None:
        self.name = weapon_description.name
        self.position = position


class ConsumableKnowledge(Copyable):
    def __init__(
        self,
        consumable_description: consumables.ConsumableDescription,
        position: coordinates.Coords,
    ) -> None:
        self.name = consumable_description.name
        self.position = position


class ArenaKnowledge(Copyable):
    def __init__(self, arena_description: arenas.ArenaDescription) -> None:
        self.arena_description = arena_description
        try:
            self.arena = arenas.Arena.load(arena_description.name)
        except FileNotFoundError:
            self.arena = None

        # TODO is there a way to get arena size without loading it?
        self.arena_size = (0, 0) if self.arena is None else self.arena.size

        self.explored_map: dict[coordinates.Coords, TileKnowledge] = {}
        self.menhir_position: Optional[coordinates.Coords] = None

    def update(
        self,
        visible_tiles: dict[coordinates.Coords, tiles.TileDescription],
        episode: int,
    ) -> None:
        # TODO remove this if we can get arena size at the very start
        max_x = max(
            [position.x for position in visible_tiles.keys()] + [self.arena_size[0]]
        )
        max_y = max(
            [position.y for position in visible_tiles.keys()] + [self.arena_size[1]]
        )
        self.arena_size = (max_x, max_y)

        for position, tile_desc in visible_tiles.items():
            if position not in self.explored_map:
                self.explored_map[position] = TileKnowledge(position)
            self.explored_map[position].update(tile_desc, episode)

            if tile_desc.type == "menhir":
                self.menhir_position = position

    def one_hot_encoding(self) -> np.ndarray:
        encoding = np.zeros((2, *self.arena_size))

        if self.arena is None:
            return encoding

        for (x, y), tile in self.arena.terrain.items():
            if tile.terrain_passable:
                encoding[0, x, y] = 1.0
            if tile.terrain_transparent:
                encoding[1, x, y] = 1.0

        return encoding


class Knowledge(Copyable):
    def __init__(self, arena_description: arenas.ArenaDescription) -> None:
        self.arena = ArenaKnowledge(arena_description)

        # controller_name -> ChampionKnowledge
        self.champions: dict[str, ChampionKnowledge] = dict()
        # coordinates -> WeaponKnowledge
        self.weapons: dict[coordinates.Coords, WeaponKnowledge] = dict()
        # coordinates -> ConsumableKnowledge
        self.consumables: dict[coordinates.Coords, ConsumableKnowledge] = dict()

        self.champions_alive: int = 0
        self.episode = 0
        self.position = coordinates.Coords(0, 0)
        self.mist_distance: int = 1_000_000
        self.visible_tiles: dict[coordinates.Coords, TileKnowledge] = {}

    @property
    def champion(self) -> ChampionKnowledge:
        return self.champions["Batman"]  # TODO get this automatically somehow?

    @property
    def last_seen_champions(self) -> dict[str, ChampionKnowledge]:
        return {
            champion_name: champion
            for champion_name, champion in self.champions.items()
            if champion.position in self.visible_tiles and champion_name != "Batman"
        }

    def update(self, knowledge: characters.ChampionKnowledge, episode: int) -> None:
        self.visible_tiles = {
            coordinates.Coords(xy[0], xy[1]): tile
            for xy, tile in knowledge.visible_tiles.items()
        }

        self.champions_alive = knowledge.no_of_champions_alive
        self.position = knowledge.position
        self.episode = episode

        # may be useful for heuristics, but not for now
        for position, tile_desc in self.visible_tiles.items():
            if tile_desc.character:
                self.champions[tile_desc.character.controller_name] = ChampionKnowledge(
                    tile_desc.character, position
                )

            if tile_desc.loot:
                self.weapons[position] = WeaponKnowledge(tile_desc.loot, position)
            elif position in self.weapons:
                del self.weapons[position]

            if tile_desc.consumable:
                self.consumables[position] = ConsumableKnowledge(
                    tile_desc.consumable, position
                )
            elif position in self.consumables:
                del self.consumables[position]

            for effect in tile_desc.effects:
                if effect.type == "mist":
                    self.mist_distance = min(
                        self.mist_distance, manhattan_distance(self.position, position)
                    )

        self.arena.update(self.visible_tiles, episode)
