from gupb.controller.norgul.misc import manhattan_dist

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles
from gupb.model import weapons

from math import inf
from typing import Dict, Set


# ---------------------
# Arena knowledge class
# ---------------------

# Represents champion's memory about arena state
class ArenaKnowledge:

    def __init__(self):
        # Global arena details
        self.width = 0
        self.height = 0

        # Detailed arena map
        # - Using a dictionary instead of list allows to disregard arena shape and simplify the code
        self._arena: dict[coordinates.Coords, tiles.TileDescription] = {}

        # Helper structures
        # - Save most important arena tiles and properties to separate variables/structures to allow for quick search for given type of thing
        self.obelisk_pos = None
        self.forest: Set[coordinates.Coords] = set()
        self.weapons: Dict[coordinates.Coords, weapons.WeaponDescription] = {}
        self.potions: Set[coordinates.Coords] = set()
        self.players: Dict[coordinates.Coords, characters.ChampionDescription] = {}
        self.any_mist = False

    # -------------------------------
    # Arena knowledge - static update
    # -------------------------------

    def clear(self) -> None:
        ''' Resets any obtained knowledge '''
        self._arena.clear()

        self.obelisk_pos = None
        self.forest.clear()
        self.weapons.clear()
        self.potions.clear()
        self.players.clear()
        self.any_mist = False
    
    def load(self, arena_path: str) -> None:
        ''' Loads and saves given arena state from a file'''

        # Reset previous arena state
        self.clear()

        # Load new state
        with open(arena_path, "r", encoding="utf-8") as file:
            for i, line in enumerate(file):
                for j, tile in enumerate(line):
                    if str.isspace(tile):
                        continue

                    coords = coordinates.Coords(j, i)
                    tile_type = arenas.TILE_ENCODING[tile] if not str.isalpha(tile) else tiles.Land
                    tile_name = tile_type.__name__.lower()
                    weapon_name = arenas.WEAPON_ENCODING[tile].__name__.lower() if str.isalpha(tile) else None

                    self._arena[coords] = tiles.TileDescription(tile_name, weapon_name, None, None, [])  # TODO sieci sie, nie ma byc [] ?

                    # Update helper structures
                    if tile_name == "forest":
                        self.forest.add(coords)
                    
                    if weapon_name is not None:
                        self.weapons[coords] = weapons.WeaponDescription(weapon_name)

                    self.width = j + 1
                
                self.height = i + 1
    
    # --------------------------------
    # Arena knowledge - dynamic update
    # --------------------------------

    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        ''' Performs arena state update based on recently observed tiles'''

        for coord, tile_info in knowledge.visible_tiles.items():
            self._arena[coord] = tile_info

            # Tile type
            if tile_info.type == "menhir":
                self.obelisk_pos = coord
            elif tile_info.type == "forest" and coord not in self.forest:
                self.forest.add(coord)

            # Weapons & potions
            if tile_info.loot is not None:
                self.weapons[coord] = tile_info.loot
            elif coord in self.weapons:
                self.weapons.pop(coord)
            
            if tile_info.consumable is not None:
                self.potions.add(coord)
            elif coord in self.potions:
                self.potions.remove(coord)
        
            # Effects
            if self._arena[coord].effects and ("mist",) in self._arena[coord].effects:
                self.any_mist = True

            # Other players
            if tile_info.character is not None:
                self.players[coord] = tile_info.character
            elif coord in self.players:
                self.players.pop(coord)

    # --------------------------------
    # Arena knowledge - simple getters
    # --------------------------------

    # Getters - tile correctness
    # - Check with respect to arena bounds
    # - NOTE: It can be used with 'in' operator, such as: if sq in arena
    def __contains__(self, tile: coordinates.Coords) -> bool:
        ''' Returns true if given tile lies inside the arena bounds, and false otherwise '''

        return 0 <= tile[0] < self.width and 0 <= tile[1] < self.height
    
    # Getters - tile info
    # - NOTE: It's recommended to use this method instead of directly accessing the arena dictionary
    def __getitem__(self, coord: coordinates.Coords) -> tiles.TileDescription | None:
        ''' A safe getter - performs bound checks and returns tile description (or None if tile is unseen).

            Allows a situation, where arena state is not loaded directly and tiles are initially set as unseen.
        '''
        # Perform bound checks
        if not self.__contains__(coord):
            raise ValueError(f"Invalid coordinate: {coord}")
        
        # Unseen tile
        if coord not in self._arena:
            return None
        
        return self._arena[coord]
    
    # Getters - adjacent squares
    def adjacent(self, sq_from: coordinates.Coords) -> list[coordinates.Coords]:
        ''' Returns all adjacent squares (which can be accessed in one move from sq_from)'''

        squares = [sq_from + dir.value for dir in characters.Facing]

        return [sq for sq in squares if 0 <= sq[0] < self.height and 0 <= sq[1] < self.width]
    
    # ----------------------------------
    # Arena knowledge - advanced getters
    # ----------------------------------

    # Getters - nearest forest tile
    def nearest_forest(self, sq_from: coordinates.Coords) -> coordinates.Coords:
        ''' Returns coordinates of the nearest forest tile (in manhattan metric) NOT OCCUPIED by any player '''

        min_distance = inf
        nearest_sq = None

        for sq in self.forest:
            distance = manhattan_dist(sq_from, sq)

            if self._arena[sq].type == "forest" and self._arena[sq].character is None and distance < min_distance:
                min_distance = distance
                nearest_sq = sq
        
        return nearest_sq