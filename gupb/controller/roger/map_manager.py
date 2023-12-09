import os

from typing import Dict, Optional, List, Tuple, Callable
from math import inf
from pathfinding.core.grid import Grid
from pathfinding.core.node import GridNode
from pathfinding.finder.a_star import AStarFinder

from gupb.controller.roger.constans_and_types import SeenWeapon, EpochNr, T, SeenEnemy
from gupb.controller.roger.utils import get_distance
from gupb.controller.roger.weapon_manager import get_weapon_cut_positions
from gupb.model import coordinates, tiles, characters
from gupb.model.arenas import Terrain, TILE_ENCODING, WEAPON_ENCODING
from gupb.model.characters import ChampionDescription, Facing, Action
from gupb.model.coordinates import Coords
from gupb.model.tiles import Land, Menhir


class MapManager:
    def __init__(self):
        self.seen_tiles: Dict[coordinates.Coords, Tuple[tiles.TileDescription, int]] = {}
        self.terrain: Optional[Terrain] = None
        self.arena_size = (50, 50)
        self.menhir_coords: Optional[coordinates.Coords] = None
        self.weapons_coords: Dict[coordinates.Coords, SeenWeapon] = {}
        self.potions_coords: Dict[coordinates.Coords, EpochNr] = {}
        self.enemies_coords: Dict[coordinates.Coords, SeenEnemy] = {}
        self.potential_attackers: Dict[coordinates.Coords, SeenEnemy] = {}
        self.mist_coords: List[coordinates.Coords] = []
        self.current_position: Optional[coordinates.Coords] = None
        self.epoch: EpochNr = 0
        self.in_cut_range = False
        self.current_cut_range_tiles: List[coordinates.Coords] = []
        self.grid: Optional[Grid] = None

    def reset(self, arena_name: str):
        self.seen_tiles = {}
        self.menhir_coords = None
        self.weapons_coords = {}
        self.load_arena(arena_name)
        self.potions_coords = {}
        self.enemies_coords = {}
        self.potential_attackers = {}
        self.mist_coords = []
        self.in_cut_range = False
        self.current_cut_range_tiles = []

    def update(self, current_position: coordinates.Coords, epoch_nr: EpochNr,
               tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        self.in_cut_range = False
        self.current_cut_range_tiles = []
        self.current_position = current_position
        self.epoch = epoch_nr
        self.seen_tiles.update(dict((x[0], (x[1], self.epoch)) for x in tiles.items()))
        self.look_for_important_items(tiles)

    def look_for_important_items(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, tile in tiles.items():
            self.check_menhir(coords, tile)
            self.check_potion(coords, tile)
            self.check_enemy(coords, tile)
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
        self.potential_attackers = {}
        if tile.character:
            if coords != self.current_position:
                self.enemies_coords[coords] = SeenEnemy(tile.character, self.epoch)
                self.check_if_potential_attacker(coords)

        else:
            self.enemies_coords.pop(coords, None)

    def check_if_potential_attacker(self, coords):
        cut_positions = get_weapon_cut_positions(self.seen_tiles, self.terrain, coords, self.enemies_coords[coords].enemy.weapon.name)
        self.current_cut_range_tiles.extend(cut_positions)
        if self.current_position in cut_positions:
            self.potential_attackers[coords] = self.enemies_coords[coords]
            self.in_cut_range = True

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

    def get_tiles_around(self, position=None, back=False) -> List[Coords]:
        if position is None:
            position = self.current_position
        tiles = [
            position + Coords(0, 1),
            position + Coords(0, -1),
            position + Coords(1, 0),
            position + Coords(-1, 0)
        ]
        if not back:
            try:
                back_coords = position - self.seen_tiles[position][0].character.facing.value
            except KeyError:
                return tiles
            for i, coord in enumerate(tiles):
                if coord == back_coords:
                    del tiles[i]
                    break
        return tiles

    def subtract_enemy_live(self, enemy: ChampionDescription):
        my = self.seen_tiles[self.current_position][0].character
        return my.health - enemy.health

    def extract_walkable_tiles(self):
        items = self.terrain.items()
        try:
            return list(filter(lambda x: isinstance(x[1], Land) or isinstance(x[1], Menhir), items))
        except Exception:
            return list(filter(lambda x: x[1][0].type == 'land' or x[1][0].type == 'menhir', items))

    def extract_walkable_coords(self, coords: List[Coords]) -> List[Coords]:
        tiles = self.terrain
        walkable_coords = []
        for coord in coords:
            tile = tiles[coord]
            if isinstance(tile, Land) or isinstance(tile, Menhir):
                seen_tile = self.seen_tiles.get(coord)
                if seen_tile:
                    if seen_tile[0].character is None:
                        walkable_coords.append(coord)
        return walkable_coords

    def build_grid(self):
        walkable_tiles_list = self.extract_walkable_tiles()
        walkable_tiles_matrix = [[0 for y in range(self.arena_size[1])] for x in range(self.arena_size[0])]

        for tile in walkable_tiles_list:
            x, y = tile[0]
            walkable_tiles_matrix[y][x] = 1

        self.grid = Grid(self.arena_size[0], self.arena_size[1], walkable_tiles_matrix)

    def map_path_to_action_list(self, current_position: Coords, path: List[GridNode], fast_mode: bool = False) -> List[characters.Action]:
        if fast_mode:
            return self.map_path_to_fast_action_list(current_position, path)
        initial_facing = self.seen_tiles[current_position][0].character.facing
        facings: List[characters.Facing] = list(
            map(lambda a: characters.Facing(Coords(a[1].x - a[0].x, a[1].y - a[0].y)), list(zip(path[:-1], path[1:]))))
        actions: List[characters.Action] = []
        for a, b in zip([initial_facing, *facings[:-1]], facings):
            actions.extend(self.map_facings_to_actions(a, b, False))
        return actions

    def map_path_to_fast_action_list(self, current_position: Coords, path: List[GridNode]) -> List[characters.Action]:
        initial_facing = self.seen_tiles[current_position][0].character.facing
        facings: List[characters.Facing] = list(
            map(lambda a: characters.Facing(Coords(a[1].x - a[0].x, a[1].y - a[0].y)), list(zip(path[:-1], path[1:]))))
        actions: List[characters.Action] = []
        for a, b in zip([initial_facing for _ in range(len(facings))], facings):
            actions.extend(self.map_facings_to_actions(a, b, True))
        return actions

    def map_facings_to_actions(self, f1: characters.Facing, f2: characters.Facing, fast_mode: bool) -> List[characters.Action]:
        if fast_mode:
            return self.map_facings_to_fast_actions(f1, f2)
        else:
            return self.map_facings_to_slow_actions(f1, f2)

    def map_facings_to_slow_actions(self, f1: characters.Facing, f2: characters.Facing) -> List[characters.Action]:
        if f1 == f2:
            return [characters.Action.STEP_FORWARD]
        elif f1.turn_left() == f2:
            return [characters.Action.TURN_LEFT, characters.Action.STEP_FORWARD]
        elif f1.turn_right() == f2:
            return [characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]
        else:
            return [characters.Action.TURN_RIGHT, characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]

    def map_facings_to_fast_actions(self, f1: characters.Facing, f2: characters.Facing) -> List[characters.Action]:
        if f1 == f2:
            return [characters.Action.STEP_FORWARD]
        elif f1.turn_left() == f2:
            return [characters.Action.STEP_LEFT]
        elif f1.turn_right() == f2:
            return [characters.Action.STEP_RIGHT]
        else:
            return [characters.Action.STEP_BACKWARD]

    def get_path(self, dest: Coords) -> List[GridNode]:
        self.build_grid()
        x, y = self.current_position
        x_dest, y_dest = dest
        finder = AStarFinder()
        path, _ = finder.find_path(self.grid.node(x, y), self.grid.node(x_dest, y_dest), self.grid)
        return path

    def get_distance_to_enemy(self, enemy_coords: Coords):
        path = self.get_path(enemy_coords)
        act_list = self.map_path_to_fast_action_list(self.current_position, path)
        return len(act_list)

    def get_safe_tiles(self) -> List[Coords]:
        coords_around = self.get_tiles_around()
        coords_available = self.extract_walkable_coords(coords_around)
        coords_available.append(self.current_position)
        tiles_available_set = set(coords_available)
        unsafe_tiles = []
        for coords, seen_enemy in self.enemies_coords.items():
            if seen_enemy.seen_epoch_nr >= self.epoch-2:
                cut_tiles = get_weapon_cut_positions(self.seen_tiles, self.terrain, coords, seen_enemy.enemy.weapon.name)
                unsafe_tiles.extend(cut_tiles)
        unsafe_tiles_set = set(unsafe_tiles)
        safe_coords = tiles_available_set.difference(unsafe_tiles_set)
        safe_coords = list(safe_coords)
        return safe_coords

    # TODO test get_coords_to_attack_in_next_round
    def get_coords_to_attack_in_next_round(self, position: Coords = None, champion_desc: ChampionDescription = None) -> Dict:
        if position is None:
            position = self.current_position
        if champion_desc is None:
            champion_desc = self.seen_tiles[self.current_position][0].character
        coords_available = self.get_possible_character_coords_in_next_round(position)
        new_coords_cut_range = {}
        for new_position in coords_available:
            if new_position in self.seen_tiles and self.seen_tiles[new_position][0].loot is not None:
                my_weapon_name = self.seen_tiles[new_position][0].loot.name
            else:
                my_weapon_name = champion_desc.weapon.name
            my_facing = champion_desc.facing
            cut_positions = get_weapon_cut_positions(self.seen_tiles, self.terrain, new_position, my_weapon_name, my_facing)
            if new_position == position:
                new_coords_cut_range[new_position] = {Action.TURN_LEFT: [],
                                                      Action.TURN_RIGHT: [],
                                                      Action.STEP_FORWARD: cut_positions}
            else:
                new_coords_cut_range[new_position] = cut_positions
        for action in (Action.TURN_LEFT, Action.TURN_RIGHT):
            my_weapon_name = champion_desc.weapon.name
            my_facing = champion_desc.facing
            if action == Action.TURN_RIGHT:
                my_new_facing = my_facing.turn_right()
            else:
                my_new_facing = my_facing.turn_left()
            cut_positions = get_weapon_cut_positions(self.seen_tiles, self.terrain, position, my_weapon_name, my_new_facing)
            new_coords_cut_range[position][action] = cut_positions
        return new_coords_cut_range

    def get_possible_character_coords_in_next_round(self, position: Coords = None, back=True):
        if position is None:
            position = self.current_position
        coords_around = self.get_tiles_around(position=position, back=back)
        coords_available = self.extract_walkable_coords(coords_around)
        coords_available.append(position)
        return coords_available


