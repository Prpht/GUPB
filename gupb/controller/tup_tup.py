from collections import defaultdict, deque
from queue import SimpleQueue
from typing import Dict, Type, Optional, List

from gupb.model import arenas, coordinates, weapons, tiles, characters

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
        self.reached_middle: bool = False
        self.direction: Optional[characters.Facing] = None
        self.moved: bool = False
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()
        self.weapon_positions = defaultdict(list)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TupTupController) and other.name == self.name:
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.identifier)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_pos = arena_description.menhir_position
        parsed_map = self.parse_map(arena_description.name)
        start = coordinates.Coords(80, 25)  # watch out, hardcoded for now
        end = coordinates.Coords(92, 11)  # watch out, hardcoded for now
        try:
            res = self.breadth_first_search(parsed_map, start, end)
            path = self.get_path(parsed_map, end, start, res)
            print("Ordered path ", path)
        except BFSException:
            print("BFS was unsuccessful, try the old method for solving the maze.")

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.__update_char_info(knowledge)

        if self.__is_enemy_in_range(knowledge.position, knowledge.visible_tiles):
            return characters.Action.ATTACK

        if not self.action_queue.empty():
            return self.action_queue.get()

        if self.direction:
            self.__avoid_obstacle(knowledge)
        elif not self.reached_middle:
            self.__move(knowledge)
        else:
            self.__guard_area()

        if not self.action_queue.empty():
            return self.action_queue.get()
        else:  # prevent the game from exploding
            return characters.Action.DO_NOTHING

    def __update_char_info(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position
        char_description = knowledge.visible_tiles[knowledge.position].character
        weapons_map = {w.__name__.lower(): w for w in [weapons.Knife, weapons.Sword, weapons.Bow,
                                                       weapons.Amulet, weapons.Axe]}
        self.weapon = weapons_map.get(char_description.weapon.name, weapons.Knife)
        self.facing = char_description.facing

    def __move(self, knowledge: characters.ChampionKnowledge) -> None:
        x_distance, y_distance = self.__calc_coords_diff(self.menhir_pos, self.position)
        if abs(x_distance) < 2 and abs(y_distance) < 2:
            self.reached_middle = True
            self.action_queue.put(characters.Action.TURN_RIGHT)
            return None

        if x_distance == 0:  # changes in vertical direction
            expected_facing = self.__get_expected_facing(y_distance, True)
        elif y_distance == 0 or abs(x_distance) <= abs(y_distance):  # changes in horizontal direction
            expected_facing = self.__get_expected_facing(x_distance, False)
        else:  # changes in vertical direction
            expected_facing = self.__get_expected_facing(y_distance, True)

        if self.facing != expected_facing:
            self.__rotate(expected_facing)
        elif self.__can_move_forward(knowledge):
            self.action_queue.put(characters.Action.STEP_FORWARD)
        else:
            self.direction = self.facing
            self.__avoid_obstacle(knowledge)

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

    def __get_expected_facing(self, distance: int, is_move_vertical: bool) -> characters.Facing:
        if is_move_vertical:
            return characters.Facing.UP if distance < 0 else characters.Facing.DOWN
        else:
            return characters.Facing.LEFT if distance < 0 else characters.Facing.RIGHT

    def __can_move_forward(self, knowledge: characters.ChampionKnowledge) -> bool:
        next_tile_coords = self.position + self.facing.value
        return next_tile_coords in knowledge.visible_tiles.keys() \
               and knowledge.visible_tiles[next_tile_coords].type == 'land'

    def __avoid_obstacle(self, knowledge):
        if self.facing == self.direction:
            if self.__can_move_forward(knowledge):
                self.direction = None
                self.moved = False
                self.action_queue.put(characters.Action.STEP_FORWARD)
            else:
                self.moved = False
                self.action_queue.put(characters.Action.TURN_RIGHT)
        else:
            if self.moved:
                self.moved = False
                self.action_queue.put(characters.Action.TURN_LEFT)
            else:
                if self.__can_move_forward(knowledge):
                    self.moved = True
                    self.action_queue.put(characters.Action.STEP_FORWARD)
                else:
                    self.moved = False
                    self.action_queue.put(characters.Action.TURN_RIGHT)

    def __guard_area(self) -> None:
        self.action_queue.put(characters.Action.TURN_RIGHT)

    def __calc_coords_diff(self, end_coords: int, start_coords: int) -> int:
        coords_dif = coordinates.sub_coords(end_coords, start_coords)
        return coords_dif

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

    def parse_map(self, name):
        # Coords(x,y) == Coords(column, row) --> parsed_map[row][column] == parsed_map[Coords.y][Coords.x]
        arena = arenas.Arena.load(name)
        self.arena_size = arena.size  # todo self declaration out of init
        columns, rows = arena.size
        parsed_map = [[0 for _ in range(columns)] for _ in range(rows)]
        for coord in arena.terrain.keys():
            curr_tile = arena.terrain[coord]
            if curr_tile.terrain_passable():
                parsed_map[coord.y][coord.x] = 1
                if curr_tile.loot is not None:
                    weapon_name = curr_tile.loot.description().name
                    self.weapon_positions[weapon_name].append(coord)
        return parsed_map

    def __get_neighbors(self, grid, coords):
        X, Y = self.arena_size
        available_cells = []
        for move in [coordinates.Coords(-1, 0), coordinates.Coords(1, 0),
                     coordinates.Coords(0, -1), coordinates.Coords(0, 1)]:
            next_coords = coords + move
            if 0 <= next_coords.x < X and 0 <= next_coords.y < Y:
                if grid[next_coords.x][next_coords.y] == 1:
                    available_cells.append(next_coords)
        return available_cells

    def breadth_first_search(self, grid, start: coordinates.Coords, goal: coordinates.Coords):
        queue = deque()
        if grid[start.x][start.y] == 1:
            queue.append(start)
        visited = set()
        path = {start: (0, start)}

        while queue:
            cell = queue.popleft()
            if cell in visited:
                continue
            if cell == goal:
                return path
            visited.add(cell)
            for neighbour in self.__get_neighbors(grid, cell):
                if neighbour not in path:
                    path[neighbour] = (path[cell][0] + 1, cell)
                queue.append(neighbour)
        raise BFSException("The shortest path wasn't found!")

    def get_path(self, graph, source, destination, path, backtrack_path=[]):  # source = end, destination = start
        if source == destination:
            return backtrack_path
        elif source not in path.keys():
            return []
        else:
            self.get_path(graph, path[source][1], destination, path, backtrack_path)
        backtrack_path.append(path[source])
        return backtrack_path

    def get_destination_facing(self, dest_coords, source_coords, facing):
        coords_diff = dest_coords - source_coords
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


class BFSException(Exception):
    pass


POTENTIAL_CONTROLLERS = [
    TupTupController('Bot'),
]
