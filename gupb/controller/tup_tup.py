from queue import SimpleQueue
from typing import Dict, Type, Optional, Tuple, List, Set

from gupb.model import arenas, coordinates, weapons, tiles, characters, games

FACING_ORDER = [characters.Facing.LEFT, characters.Facing.UP, characters.Facing.RIGHT, characters.Facing.DOWN]


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
        self.has_calculated_path: bool = False
        self.path: List = []
        self.bfs_goal: coordinates.Coords = None
        self.bfs_potential_goals: Set[coordinates.Coords] = set()
        self.bfs_potential_goals_visited: Set[coordinates.Coords] = set()
        self.map: Optional[arenas.Terrain] = None
        self.map_size: Optional[Tuple[int, int]] = None
        self.hiding_spot: coordinates.Coords = None
        self.mist_radius: int = 0
        self.episode: int = 0
        self.max_num_of_episodes: int = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TupTupController) and other.name == self.name:
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.identifier)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        arena = arenas.Arena.load(arena_description.name)
        self.map = arena.terrain
        self.map_size = arena.size
        self.mist_radius = int(self.map_size[0] * 2 ** 0.5) + 1
        self.max_num_of_episodes = (self.mist_radius - 1) * games.MIST_TTH
        self.menhir_pos = arena_description.menhir_position
        self.bfs_goal = self.menhir_pos
        self.bfs_potential_goals_visited.add(self.menhir_pos)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.episode += 1
        try:
            self.__update_char_info(knowledge)

            if self.episode == 1 and self.__needs_to_hide():
                self.__go_to_hiding_spot()

            if self.__is_enemy_in_range(knowledge.position, knowledge.visible_tiles):
                return characters.Action.ATTACK

            if not self.action_queue.empty():
                return self.action_queue.get()

            if not self.has_calculated_path:
                start, end = self.position, self.bfs_goal
                self.__calculate_optimal_path(start, end)

                if len(self.path) > 0:  # the path was found
                    self.has_calculated_path = True
                else:
                    neighbors = self.__get_neighbors(self.bfs_goal)
                    for neighbor in neighbors:
                        if neighbor not in self.bfs_potential_goals_visited:
                            self.bfs_potential_goals.add(neighbor)
                    if self.bfs_potential_goals:
                        self.bfs_goal = self.bfs_potential_goals.pop()
                        self.bfs_potential_goals_visited.add(self.bfs_goal)

            if not self.action_queue.empty():
                return self.action_queue.get()

            if len(self.path) > 1 and self.__has_to_move():
                self.__add_moves(2)
            else:  # the destination is reached
                self.__guard_area()

            if not self.action_queue.empty():
                return self.action_queue.get()

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

    def __needs_to_hide(self) -> bool:
        quarter = (self.position[0] // (self.map_size[0] / 2), self.position[1] // (self.map_size[1] / 2))
        if self.menhir_pos[0] // (self.map_size[0] / 2) == quarter[0] and \
                self.menhir_pos[1] // (self.map_size[1] / 2) == quarter[1]:
            start_x = self.map_size[0] - 1 if quarter[0] > 0 else 0
            start_y = self.map_size[1] - 1 if quarter[1] > 0 else 0
            corner = {(start_x, start_y)}
            while not self.hiding_spot:
                for t in corner:
                    if t in self.map and self.map[t].terrain_passable():
                        self.hiding_spot = coordinates.Coords(t[0], t[1])
                        break
                corner.update([(t[0] + d[0], t[1] + d[1]) for t in corner for d in [(0, 1), (0, -1), (1, 0), (-1, 0)]])
            return True
        else:
            return False

    def __go_to_hiding_spot(self) -> None:
        start, end = self.position, self.hiding_spot
        self.__calculate_optimal_path(start, end)
        self.path.append(end)
        self.__add_moves(200)

    def __rotate(self, expected_facing: characters.Facing, starting_facing: characters.Facing = None) -> None:
        curr_facing_index = FACING_ORDER.index(self.facing if not starting_facing else starting_facing)
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

    def __has_to_move(self) -> bool:
        return self.episode >= self.max_num_of_episodes - len(self.path) * 5

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
        except KeyError:    # tile was not visible
            return False

    def __get_neighbors(self, coords):
        available_cells = []
        for facing in characters.Facing:
            next_coords = coords + facing.value
            if next_coords in self.map and self.map[coords].terrain_passable():
                available_cells.append(next_coords)
        return available_cells

    def __breadth_first_search(self, start_coords: coordinates.Coords, end_coords: coordinates.Coords) -> \
            Dict[coordinates.Coords, Tuple[int, coordinates.Coords]]:
        queue = SimpleQueue()
        if self.map[start_coords].terrain_passable():
            queue.put(start_coords)
        visited = set()
        path = {start_coords: start_coords}

        while not queue.empty():
            cell = queue.get()
            if cell in visited:
                continue
            if cell == end_coords:
                return path
            visited.add(cell)
            for neighbour in self.__get_neighbors(cell):
                if neighbour not in path:
                    path[neighbour] = cell
                queue.put(neighbour)
        raise BFSException("The shortest path wasn't found!")

    def __backtrack_path(self, end_coords: coordinates.Coords, start_coords: coordinates.Coords, path: Dict,
                         final_path: List):
        if end_coords == start_coords:
            return self.facing, end_coords
        elif end_coords not in path.keys():
            raise PathFindingException
        else:
            next_coord = path[end_coords]
            prev_facing, prev_coords = self.__backtrack_path(next_coord, start_coords, path, final_path)
            next_facing = characters.Facing(end_coords - next_coord)
            final_path.append(next_coord)
            return next_facing, next_coord

    def __get_rotations_number(self, current_facing: characters.Facing, next_facing: characters.Facing) -> int:
        curr_facing_index = FACING_ORDER.index(current_facing)
        next_facing_index = FACING_ORDER.index(next_facing)
        diff = next_facing_index - curr_facing_index
        if diff < 0:
            diff += len(FACING_ORDER)
        if diff % 2 != 0:
            return 1
        elif diff == 2:
            return 2
        return 0

    def __calculate_optimal_path(self, start_coords: coordinates.Coords, end_coords: coordinates.Coords):
        try:
            bfs_res = self.__breadth_first_search(start_coords, end_coords)
            final_path = []
            self.__backtrack_path(end_coords, start_coords, bfs_res, final_path)
            self.path = final_path
        except (BFSException, PathFindingException) as e:
            pass

    def __add_moves(self, number_of_moves=1) -> None:
        starting_facing = None
        for _ in range(number_of_moves):
            if len(self.path) < 2:
                break
            start_coords = self.path.pop(0)
            end_coords = self.path[0]
            starting_facing = self.__move(start_coords, end_coords, starting_facing)

    def __move(self, start_coords: coordinates.Coords, end_coords: coordinates.Coords,
               starting_facing: characters.Facing = None) -> characters.Facing:
        try:
            destination_facing = self.__get_destination_facing(end_coords, start_coords)
            self.__rotate(destination_facing, starting_facing)
            self.action_queue.put(characters.Action.STEP_FORWARD)
            return destination_facing
        except Exception:
            pass

    def __get_destination_facing(self, end_coords: coordinates.Coords,
                                 start_coords: coordinates.Coords) -> characters.Facing:
        coords_diff = end_coords - start_coords
        if coords_diff.y == 0:
            if coords_diff.x < 0:
                return characters.Facing.LEFT
            if coords_diff.x > 0:
                return characters.Facing.RIGHT
        elif coords_diff.x == 0:
            if coords_diff.y < 0:
                return characters.Facing.UP
            if coords_diff.y > 0:
                return characters.Facing.DOWN
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
