from collections import defaultdict, deque
from queue import SimpleQueue
from typing import Dict, Type, Optional, Tuple, List

from gupb.model import arenas, coordinates, weapons, tiles, characters

import random

FACING_ORDER = [characters.Facing.LEFT, characters.Facing.UP, characters.Facing.RIGHT, characters.Facing.DOWN]
ALLOWED_TILES = {tiles.Land}
WEAPON_TYPES = arenas.WEAPON_ENCODING.keys()


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class TupTupController:
    def __init__(self, name_suffix):
        self.identifier: str = "TupTup" + name_suffix
        self.menhir_pos: coordinates.Coords = None
        self.facing: Optional[characters.Facing] = None
        self.position: coordinates.Coords = None
        self.weapon: Type[weapons.Weapon] = weapons.Knife
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()
        self.weapon_positions = defaultdict(list)
        self.has_calculated_path: bool = False
        self.parsed_map: Optional[list[list[int]]] = None
        self.path: List = []
        self.arena_size: Optional[tuple[int, int]] = None
        self.bfs_goal: coordinates.Coords = None
        self.bfs_potential_goals: set[coordinates.Coords] = set()
        self.bfs_potential_goals_visited: set[coordinates.Coords] = set()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TupTupController) and other.name == self.name:
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.identifier)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_pos = arena_description.menhir_position
        self.bfs_goal = self.menhir_pos
        try:
            self.bfs_potential_goals_visited.add(self.menhir_pos)
            self.parsed_map = self.__parse_map(arena_description.name)
        except Exception:
            pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.__update_char_info(knowledge)

            if not self.has_calculated_path:
                start, end = self.position, self.bfs_goal
                self.__calculate_optimal_path(start, end)
                if len(self.path) > 0:  # the calculations were successful
                    self.has_calculated_path = True
                elif self.parsed_map:
                    neighbors = self.__get_neighbors(self.parsed_map, self.bfs_goal)
                    for neighbor in neighbors:
                        if neighbor not in self.bfs_potential_goals_visited:
                            self.bfs_potential_goals.add(neighbor)
                    if self.bfs_potential_goals:
                        self.bfs_goal = self.bfs_potential_goals.pop()
                        self.bfs_potential_goals_visited.add(self.bfs_goal)

            if self.__is_enemy_in_range(knowledge.position, knowledge.visible_tiles):
                return characters.Action.ATTACK

            if not self.action_queue.empty():
                return self.action_queue.get()

            if len(self.path) > 1:
                instr1 = self.path.pop(0)[1]
                instr2 = self.path[0][1]
                self.__new_move(instr1, instr2)
            else:  # the destination is reached
                self.__guard_area()

            return characters.Action.DO_NOTHING
        except Exception:
            return characters.Action.DO_NOTHING

    def __update_char_info(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position
        char_description = knowledge.visible_tiles[knowledge.position].character
        weapons_map = {w.__name__.lower(): w for w in [weapons.Knife, weapons.Sword, weapons.Bow,
                                                       weapons.Amulet, weapons.Axe]}
        self.weapon = weapons_map.get(char_description.weapon.name, weapons.Knife)
        self.facing = char_description.facing

    def __rotate(self, expected_facing: characters.Facing) -> None:
        curr_facing_index = FACING_ORDER.index(self.facing)
        expected_facing_index = FACING_ORDER.index(expected_facing)

        diff_expected_curr = expected_facing_index - curr_facing_index
        if diff_expected_curr < 0:
            diff_expected_curr += len(FACING_ORDER)

        if diff_expected_curr == 1:
            self.action_queue.put(characters.Action.TURN_RIGHT)
        elif diff_expected_curr == 2:
            self.action_queue.put(characters.Action.TURN_RIGHT)
            self.action_queue.put(characters.Action.TURN_RIGHT)
        elif diff_expected_curr == 3:
            self.action_queue.put(characters.Action.TURN_LEFT)

    def __guard_area(self) -> None:
        self.action_queue.put(characters.Action.TURN_RIGHT)

    def __is_enemy_in_range(self, position: coordinates.Coords,
                            visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
        try:
            if issubclass(self.weapon, weapons.LineWeapon):
                weapon_reach = self.weapon.reach()
                tile_to_check = position
                for _ in range(1, self.weapon.reach() + 1):
                    tile_to_check = tile_to_check + self.facing.value
                    if visible_tiles[tile_to_check].character:
                        return True
            elif isinstance(self.weapon, weapons.Amulet):
                for tile in [position + (1, 1), position + (-1, 1), position + (1, -1), position + (-1, -1)]:
                    if tile in visible_tiles and visible_tiles[tile].character:
                        return True
            elif isinstance(self.weapon, weapons.Axe):
                tiles_to_check = [coordinates.Coords(self.facing.value.x, i) for i in [-1, 0, 1]] \
                    if self.facing.value.x != 0 else [coordinates.Coords(i, self.facing.value.y) for i in [-1, 0, 1]]
                for tile in tiles_to_check:
                    if tile in visible_tiles and visible_tiles[position + self.facing.value].character:
                        return True
            else:
                return False
        except KeyError:
            # tile was not visible
            return False

    def __parse_map(self, name):
        # Coords(x,y) == Coords(column, row) --> parsed_map[row][column] == parsed_map[Coords.y][Coords.x]
        arena = arenas.Arena.load(name)
        self.arena_size = arena.size
        columns, rows = arena.size
        parsed_map = [[0 for _ in range(columns)] for _ in range(rows)]
        for coord in arena.terrain.keys():
            curr_tile = arena.terrain[coord]
            if curr_tile.terrain_passable():
                parsed_map[coord.y][coord.x] = 1
                if curr_tile.loot is not None:
                    weapon_name = curr_tile.loot.description().name
                    self.weapon_positions[weapon_name].append(coordinates.Coords(coord.y, coord.x))
        return parsed_map

    def __get_neighbors(self, grid, coords):
        y, x = self.arena_size
        available_cells = []
        for move in [coordinates.Coords(-1, 0), coordinates.Coords(1, 0),
                     coordinates.Coords(0, -1), coordinates.Coords(0, 1)]:
            next_coords = coords + move
            if 0 <= next_coords.x < x and 0 <= next_coords.y < y:
                if grid[next_coords.x][next_coords.y] == 1:
                    available_cells.append(next_coords)
        return available_cells

    def __breadth_first_search(self, start_coords: coordinates.Coords, end_coords: coordinates.Coords) -> \
            Dict[coordinates.Coords, Tuple[int, coordinates.Coords]]:
        queue = deque()
        if self.parsed_map[start_coords.x][start_coords.y] == 1:
            queue.append(start_coords)
        visited = set()
        path = {start_coords: (0, start_coords)}

        while queue:
            cell = queue.popleft()
            if cell in visited:
                continue
            if cell == end_coords:
                return path
            visited.add(cell)
            for neighbour in self.__get_neighbors(self.parsed_map, cell):
                if neighbour not in path:
                    path[neighbour] = (path[cell][0] + 1, cell)
                queue.append(neighbour)
        raise BFSException("The shortest path wasn't found!")

    def __get_path(self, end_coords: coordinates.Coords, start_coords: coordinates.Coords, path: Dict):
        if end_coords == start_coords:
            return 0, self.facing, end_coords
        elif end_coords not in path.keys():
            raise PathFindingException
        else:
            next = path[end_coords][1]
            prev_steps, prev_facing, prev_coords = self.__get_path(next, start_coords, path)
            diff = end_coords - next
            next_facing = characters.Facing(coordinates.Coords(diff.y, diff.x))
            rotations_number = self.__get_rotations_number(prev_facing, next_facing)
            self.path.append((prev_steps, next))
            steps = prev_steps + 1 + rotations_number
            return steps, next_facing, next

    def __get_rotations_number(self, current_facing: characters.Facing, next_facing: characters.Facing) -> int:
        curr_facing_index = FACING_ORDER.index(current_facing)
        next_facing_index = FACING_ORDER.index(next_facing)
        diff = next_facing_index - curr_facing_index
        if diff < 0:
            diff += len(FACING_ORDER)

        if diff == 1 or diff == 3:
            return 1
        elif diff == 2:
            return 2
        return 0

    def __calculate_optimal_path(self, start_coords: coordinates.Coords, end_coords: coordinates.Coords) -> bool:
        start_swapped = coordinates.Coords(start_coords.y, start_coords.x)
        end_swapped = coordinates.Coords(end_coords.y, end_coords.x)
        try:
            bfs_res = self.__breadth_first_search(start_swapped, end_swapped)
            self.__get_path(end_swapped, start_swapped, bfs_res)
        except (BFSException, PathFindingException) as e:
            pass

    def __new_move(self, start_coords: coordinates.Coords, end_coords: coordinates.Coords):
        try:
            destination_facing = self.__get_destination_facing(end_coords, start_coords)
            self.__rotate(destination_facing)
            self.action_queue.put(characters.Action.STEP_FORWARD)
        except Exception:
            pass

    def __get_destination_facing(self, end_coords: coordinates.Coords,
                                 start_coords: coordinates.Coords) -> characters.Facing:
        coords_diff = end_coords - start_coords
        if coords_diff.y == 0:
            if coords_diff.x < 0:
                return characters.Facing.UP
            if coords_diff.x > 0:
                return characters.Facing.DOWN
        elif coords_diff.x == 0:
            if coords_diff.y < 0:
                return characters.Facing.LEFT
            if coords_diff.y > 0:
                return characters.Facing.RIGHT
        else:
            # one of the numbers SHOULD be 0, otherwise sth is wrong with the BFS result
            raise (Exception("The coordinates are not one step away from each other"))

    @property
    def name(self) -> str:
        return self.identifier

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.YELLOW


class BFSException(Exception):
    pass


class PathFindingException(Exception):
    pass


POTENTIAL_CONTROLLERS = [
    TupTupController('Bot'),
]
