import random
from typing import Optional

import numpy as np

import heapq

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model.coordinates import Coords, sub_coords, add_coords
from gupb.model.effects import Mist

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.ATTACK,
    characters.Action.ATTACK,
    characters.Action.ATTACK,
]

DIRECTIONS = [(-1, 0), (0, 1), (1, 0), (0, -1)]

CHECKPOINT_TILES = [
    Coords(3, 2),
    Coords(6, 11),
    Coords(16, 17),
    Coords(21, 8),
    Coords(4, 14),
]


weapon_hitboxes = {

}


class RoombaController(controller.Controller):
    def __init__(self, first_name: str = "Roomba"):
        self.current_weapon = 'knife'
        self.facing: Optional[Facing] = None
        self.first_name: str = first_name
        self.last_position: Coords = Coords(0, 0)
        self.position: Coords = Coords(0, 0)
        self.menhir = None

        self.path = []

        self.map = """========================
=####.##=C...====....===
==#A...#==....====..=@@=
==.S....==...@==......@=
==#....#===..@@@.=.....=
=##....#====..@..#.#...=
=####.##====......M#=..=
==.....=====.....#.....=
==.###.@.#.==..#.#.#...=
===#.#....@==....#.#...=
=....#...@@.......===..=
=###..B...@.=...====.=.=
=#...##.##..===...==...=
=#...#==.#.===........#=
=#..S#=.....==........@=
=#...#==...===##.###...=
=#.###=..#..==#....#==.=
=....=.......=#BA...====
==..==....@........#====
==.....@.@#@..##.###====
=====..#@@#....M..======
=.....@###....##.#======
=C====@@....=.....======
========================""".split('\n')

        self.tiles_to_visit = CHECKPOINT_TILES.copy()

        self.target_tile = random.choice(self.tiles_to_visit)

        self.orientation_set = False

        self.step_back = None

        self.valid_weapons = ['knife', 'axe', 'sword', 'bow_loaded', 'bow_unloaded']
        self.weapon_priority = {
            'bow_loaded': 0,
            'bow_unloaded': 0,
            'sword': 0,
            'axe': 0,
            'knife': 4
        }
        self.acceptable_weapon_priority = 1
        self.turn_threshold = 4
        self.total_turns = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RoombaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        #print(knowledge)
        self.total_turns += 1
        #print(self.path)
        if self.total_turns % self.turn_threshold == 0:
            self.acceptable_weapon_priority += 1

        if self.step_back is not None:
            step = self.step_back
            self.step_back = None
            return step

        visible_tiles = list(knowledge.visible_tiles.keys())
        self.last_position = self.position
        self.position = knowledge.position
        self.current_weapon = knowledge.visible_tiles[self.position].character.weapon.name
        #print(self.current_weapon)
        self.facing = knowledge.visible_tiles[self.position].character.facing
        # print(self.position, self.last_position)
        if self.position != self.last_position and self.path:
            self.path.pop(0)

        hittable_tiles = self.get_current_weapon_hit_tiles(knowledge.visible_tiles)
        #print(hittable_tiles)
        for tile in hittable_tiles:
           if knowledge.visible_tiles[tile].character is not None and knowledge.visible_tiles[tile].type != "forest":
               return characters.Action.ATTACK
        # if knowledge.visible_tiles[self.tile_forward_from_x(self.position)].character is not None:
        #     return characters.Action.ATTACK

        if knowledge.visible_tiles[self.tile_left_from_x(self.position)].character is not None:
            return characters.Action.TURN_LEFT

        if knowledge.visible_tiles[self.tile_right_from_x(self.position)].character is not None:
            return characters.Action.TURN_RIGHT

        if self.position == self.menhir:
            if knowledge.visible_tiles[self.tile_forward_from_x(self.position)].consumable is not None:
                self.step_back = characters.Action.STEP_BACKWARD
                return characters.Action.STEP_FORWARD
            if knowledge.visible_tiles[self.tile_left_from_x(self.position)].consumable is not None:
                self.step_back = characters.Action.STEP_RIGHT
                return characters.Action.STEP_LEFT
            if knowledge.visible_tiles[self.tile_right_from_x(self.position)].consumable is not None:
                self.step_back = characters.Action.STEP_LEFT
                return characters.Action.STEP_RIGHT

            return random.choice(POSSIBLE_ACTIONS)

        if self.menhir is None:
            self.menhir = self.find_menhir(knowledge)
        if self.menhir and self.current_weapon in self.valid_weapons:

            if knowledge.visible_tiles[self.tile_left_from_x(self.position)].consumable is not None:
                self.step_back = characters.Action.STEP_RIGHT
                return characters.Action.STEP_LEFT
            if knowledge.visible_tiles[self.tile_right_from_x(self.position)].consumable is not None:
                self.step_back = characters.Action.STEP_LEFT
                return characters.Action.STEP_RIGHT

            current_priority = self.weapon_priority.get(self.current_weapon, float('inf'))
            if current_priority <= self.acceptable_weapon_priority:
                if not self.path:
                    self.path = self.dijkstra(self.position, self.menhir)[1:]
                return self.go_to(self.path[0])

        mists_list = self._get_mist_position(knowledge)

        if self.position == self.target_tile:
            self.tiles_to_visit.remove(self.target_tile)
            if not self.tiles_to_visit:
                self.tiles_to_visit = CHECKPOINT_TILES.copy()
            self.target_tile = random.choice(self.tiles_to_visit)

        if not mists_list:
            # go to centre + random turns (?)
            if knowledge.visible_tiles[self.tile_left_from_x(self.position)].consumable is not None:
                self.step_back = characters.Action.STEP_RIGHT
                return characters.Action.STEP_LEFT
            if knowledge.visible_tiles[self.tile_right_from_x(self.position)].consumable is not None:
                self.step_back = characters.Action.STEP_LEFT
                return characters.Action.STEP_RIGHT
            if not self.path:
                self.path = self.dijkstra(self.position, self.target_tile)[1:]

            return self.go_to(self.path[0])

        # uciekaj przed mgla
        mist_closest = self._get_closest_tile(mists_list)
        move_vector = self._calculate_vector(mist_closest, self.position)
        return random.choice(POSSIBLE_ACTIONS)


    def get_current_weapon_hit_tiles(self, visible_tiles):
        hittable_tiles = []
        #print("aaaa")
        if self.current_weapon == 'knife':
            x = self.tile_forward_from_x(self.position)
            if x in visible_tiles:
                hittable_tiles.append(x)
        elif self.current_weapon == 'sword':
            x = self.position
            for _ in range(3):
                x = self.tile_forward_from_x(x)
                if x in visible_tiles:
                    hittable_tiles.append(x)
        elif self.current_weapon == 'axe':
            x = self.tile_forward_from_x(self.position)
            xl = self.tile_left_from_x(x)
            xr = self.tile_right_from_x(x)
            if x in visible_tiles:
                hittable_tiles.append(x)

            if xl in visible_tiles:
                hittable_tiles.append(xl)

            if xr in visible_tiles:
                hittable_tiles.append(xr)
        elif self.current_weapon == 'bow_unloaded' or self.current_weapon == 'bow_loaded':
            x = self.tile_forward_from_x(self.position)
            while x in visible_tiles:
                hittable_tiles.append(x)
                x = self.tile_forward_from_x(x)
        else:
            pass
        #print(hittable_tiles)
        return hittable_tiles
    ##'knife', 'sword', 'axe', 'bow_unloaded', 'bow_loaded'

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.facing: Optional[Facing] = None
        self.last_position: Coords = Coords(0, 0)
        self.position: Coords = Coords(0, 0)
        self.menhir = None

        self.path = []

        self.tiles_to_visit = CHECKPOINT_TILES.copy()

        self.target_tile = random.choice(self.tiles_to_visit)

        self.orientation_set = False

        self.current_weapon = 'knife'
        self.total_turns = 0
        self.acceptable_weapon_priority = 1

    def _get_mist_position(self, knowledge: characters.ChampionKnowledge) -> list[Coords]:
        mist_coordinates = []
        for coordinates, tile in knowledge.visible_tiles.items():
            effects = tile.effects
            if any(isinstance(e, Mist) for e in effects):
                mist_coordinates.append(coordinates)

        return mist_coordinates

    def go_to(self, target: Coords):
        vec = sub_coords(target, self.position)
        # print("goto", target)
        if self.facing.value == vec:
            return characters.Action.STEP_FORWARD
        return characters.Action.TURN_LEFT

    def _get_closest_tile(self, tiles_list: list[Coords]) -> Coords:
        position_arr = np.array([self.position.x, self.position.y])
        tile_arr = np.array([[coord.x, coord.y] for coord in tiles_list])
        return tiles_list[np.argmin(np.linalg.norm(tile_arr - position_arr, axis=1))]

    def _calculate_vector(self, coor_A: Coords, coor_B: Coords) -> np.ndarray:
        return np.array([coor_B.x - coor_A.x, coor_B.y - coor_A.y])

    def find_menhir(self, knowledge: characters.ChampionKnowledge) -> Optional[Coords]:
        for coord, tile_description in knowledge.visible_tiles.items():
            if tile_description.type == 'menhir':
                self.path = []
                return coord
        return None

    def in_bounds(self, x, y, width, height):
        return 0 <= x < height and 0 <= y < width

    def is_walkable(self, char):
        return char == '.' or char.isalpha() or char == '@'

    def dijkstra(self, start: Coords, goal: Coords) -> list[Coords]:
        map_data = self.map
        height = len(map_data)
        width = len(map_data[0])
        queue = [(0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0}

        while queue:
            current_cost, current = heapq.heappop(queue)

            if current == goal:
                path = []
                while current:
                    path.append(current)
                    current = came_from[current]
                return path[::-1]

            for dx, dy in DIRECTIONS:
                nx, ny = current.x + dx, current.y + dy
                if self.in_bounds(nx, ny, width, height):
                    char = map_data[ny][nx]
                    if self.is_walkable(char):
                        neighbor = Coords(nx, ny)
                        new_cost = cost_so_far[current] + 1
                        if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                            cost_so_far[neighbor] = new_cost
                            heapq.heappush(queue, (new_cost, neighbor))
                            came_from[neighbor] = current

        return [start]

    def tile_forward_from_x(self, x):
        return add_coords(x, self.facing.value)

    def tile_left_from_x(self, x):
        return add_coords(x, self.facing.turn_left().value)

    def tile_right_from_x(self, x):
        return add_coords(x, self.facing.turn_right().value)

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ROOMBA


