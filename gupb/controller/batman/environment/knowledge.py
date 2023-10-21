from typing import Optional

from gupb.model import arenas, tiles, characters, weapons, coordinates, consumables


class TileKnowledge:
    def __init__(self, coords: coordinates.Coords):
        self.coords = coords
        self.type: Optional[str] = None
        self.last_seen: Optional[
            int
        ] = None  # TODO should we store it as -1 instead of None?
        self.weapon: Optional[weapons.WeaponDescription] = None
        self.character: Optional[characters.ChampionDescription] = None
        self.consumable: Optional[consumables.ConsumableDescription] = None

        # effects (are there any other?)
        self.mist: bool = False
        self.attacked: bool = False

    def update(self, tile: tiles.TileDescription, episode: int) -> None:
        self.last_seen = episode
        self.type = tile.type
        self.weapon = tile.loot
        self.character = tile.character
        self.consumable = tile.consumable

        self.mist = any([effect.type == "mist" for effect in tile.effects])
        self.attacked = any([effect.type == "weaponcut" for effect in tile.effects])


class ArenaKnowledge:
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
            [position[0] for position in visible_tiles.keys()] + [self.arena_size[0]]
        )
        max_y = max(
            [position[1] for position in visible_tiles.keys()] + [self.arena_size[1]]
        )
        self.arena_size = (max_x, max_y)

        for position, tile_desc in visible_tiles.items():
            if position not in self.explored_map:
                self.explored_map[position] = TileKnowledge(position)
            self.explored_map[position].update(tile_desc, episode)

            if tile_desc.type == "menhir":
                self.menhir_position = position


class Knowledge:
    def __init__(self, arena_description: arenas.ArenaDescription) -> None:
        self.arena = ArenaKnowledge(arena_description)
        # self.champions: dict[str, tuple[characters.ChampionDescription]] = dict()
        # self.champions_positions: dict[str, coordinates.Coords] = dict()
        self.champions_alive: int = 0
        self.episode = 0
        self.position = coordinates.Coords(0, 0)

    def update(self, knowledge: characters.ChampionKnowledge, episode: int) -> None:
        self.champions_alive = knowledge.no_of_champions_alive
        self.position = knowledge.position
        self.episode = episode

        # may be useful for heuristics, but not for now
        # for position, tile_desc in knowledge.visible_tiles.items():
        #     if tile_desc.character:
        #         self.champions[tile_desc.character.controller_name] = tile_desc.character
        #         self.champions_positions[tile_desc.character.controller_name] = position

        self.arena.update(knowledge.visible_tiles, episode)
