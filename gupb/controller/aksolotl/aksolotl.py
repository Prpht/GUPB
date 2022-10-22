import random
import re
from gupb.model.characters import Action
import numpy as np

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates as coo
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]
DIRS_COORDS = {
    "UP": (0, -1),
    "RIGHT": (1, 0),
    "DOWN": (0, 1),
    "LEFT": (-1, 0),
}
COORDS_DIRS = {
    coo.Coords(0, -1): "UP",
    coo.Coords(1, 0): "RIGHT",
    coo.Coords(0, 1): "DOWN",
    coo.Coords(-1, 0): "LEFT",
}

TILES_VALUES = {"sea": 0, "wall": 0, "menhir": 1, "land": 1, "weapon": 100}


class AksolotlController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.position = None
        self.knowledge = None
        self.facing = None
        self.neighbors = []
        self.neighbors_types = dict()
        self.possible_tiles = []
        self.weapon_position = None
        self.menhir_position = None
        self.temp_target = None
        self.action_queue = []
        self.mist_positions = []
        self.map = np.ones((100, 100))
        self.recommended_path = []
        self.blocked = False
        self.prev_facing = None
        self.previous_position = None
        self.seen_menhir = False
        self.armed = False
        self.recalculate_path = False
        self.on_menhir = False
        self.reached_target = False
        self.store_map_before_mist = None
        self.largest_x = 0
        self.largest_y = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AksolotlController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def further_point(self, position1, position2):
        if position1 is None:
            return position2
        if position2 is None:
            return position1
        diff1 = coo.Coords(self.position[0], self.position[1]) - coo.Coords(
            position1[0], position1[1]
        )
        diff2 = coo.Coords(self.position[0], self.position[1]) - coo.Coords(
            position2[0], position2[1]
        )
        if (abs(diff1.x) + abs(diff1.y)) > (abs(diff2.x) + abs(diff2.y)):
            return position1
        else:
            return position2

    def update_map(self):
        for position, tile in self.knowledge.visible_tiles.items():
            x, y = position[0], position[1]
            if x > self.largest_x:
                self.largest_x = x
            if y > self.largest_y:
                self.largest_y = y
                # TODO add automatic updating of the map's width and height
            if tile.type in ["wall", "sea"]:
                self.map[y, x] = TILES_VALUES[tile.type]
                if (x, y) in self.recommended_path:
                    self.recalculate_path = True

            if tile.type == "menhir":
                self.menhir_position = coo.Coords(position[0], position[1])
            if (
                tile.type == "land"
                and (self.menhir_position is None)
                and (self.weapon_position is None)
            ):
                if self.further_point(self.temp_target, position) == position:
                    self.temp_target = coo.Coords(position[0], position[1])
            if tile.loot and tile.loot != "knife":
                self.map[y, x] = TILES_VALUES["weapon"]
                if self.weapon_position is None:
                    self.temp_target = coo.Coords(position[0], position[1])
                    self.weapon_position = coo.Coords(position[0], position[1])
            if tile.effects != []:
                if (
                    self.store_map_before_mist is not None
                ):  # which means we preserved map and can cut it
                    self.map[:, y] = 0
                    self.map[x, :] = 0
                self.mist_positions.append((position[0], position[1]))

    def detect_opponent(self):
        for n in self.neighbors:
            if coo.Coords(n[0], n[1]) in list(self.knowledge.visible_tiles.keys()):
                if self.knowledge.visible_tiles[coo.Coords(n[0], n[1])].character:
                    return coo.Coords(n[0], n[1])
        return None

    def check_around_for(self, type):
        for n in self.neighbors:
            if coo.Coords(n[0], n[1]) in list(self.knowledge.visible_tiles.keys()):
                info_about = self.knowledge.visible_tiles[coo.Coords(n[0], n[1])]
                if info_about.type == type:
                    return coo.Coords(n[0], n[1])
        return None

    def closest_point(self, coords_list):
        closest_point = coo.Coords(coords_list[0][0], coords_list[0][1])
        diff = coo.Coords(self.position[0], self.position[1]) - closest_point
        closest_dist = abs(diff.x) + abs(diff.y)
        for c in coords_list:
            diff = coo.Coords(self.position[0], self.position[1]) - coo.Coords(
                c[0], c[1]
            )
            if (abs(diff.x) + abs(diff.y)) < closest_dist:
                closest_point = coo.Coords(c[0], c[1])
        return closest_point

    """def approximate_mist(self):
        # cuts visible map to approximated boundaries
        closest_mist = self.closest_point(self, self.mist_positions)
        safe_boundaries_x = closest_mist[0]
        safe_boundaries_y = closest_mist[1]
        if safe_boundaries_x >= self.map.shape[1]//2:
            if safe_boundaries_y >= self.map.shape[0]//2:
                self.map = """

    def mist_strategy(self):
        safe_boundaries = self.approximate_mist()
        centre = (self.map.shape[1] // 2, self.map.shape[0] // 2)
        if self.menhir_position:
            self.calculate_path(self.menhir_position)
            if self.recommended_path != []:
                self.follow_path(self.recommended_path)
                return self.act_update()
            if self.recommended_path == []:
                self.calculate_path(centre[0], centre[1])
                self.follow_path(self.recommended_path)
                return self.act_update()
        else:
            self.calculate_path(centre[0], centre[1])
            self.follow_path(coo.Coords(self.recommended_path))
            return self.act_update()

    def update_neighbors(self):
        return [
            coo.Coords(self.position[0], self.position[1]) + coo.Coords(1, 0),
            coo.Coords(self.position[0], self.position[1]) + coo.Coords(0, 1),
            coo.Coords(self.position[0], self.position[1]) + coo.Coords(-1, 0),
            coo.Coords(self.position[0], self.position[1]) + coo.Coords(0, -1),
        ]

    def update_neighbors_types(self):
        self.neighbors_types = dict.fromkeys(self.neighbors)
        possible_tiles = self.neighbors.copy()
        for n in self.neighbors:
            if coo.Coords(n[0], n[1]) in self.knowledge.visible_tiles.keys():
                curr_type = self.knowledge.visible_tiles[coo.Coords(n[0], n[1])].type
                self.neighbors_types[n] = curr_type
                if curr_type in ["wall", "sea"]:
                    possible_tiles.remove(coo.Coords(n[0], n[1]))
        self.possible_tiles = possible_tiles

    def follow_path(self, path):
        if (not path) or (
            len(path) == 1
            and (
                self.position
                == coo.Coords(self.recommended_path[0][0], self.recommended_path[0][1])
            )
        ):  # change it
            return

        if self.position == coo.Coords(
            self.recommended_path[0][0], self.recommended_path[0][1]
        ):
            self.recommended_path.pop(0)
        next_position = path[0]
        self.move_to(next_position)

    def move_to(self, destination_coords):
        diff = coo.Coords(destination_coords[0], destination_coords[1]) - coo.Coords(
            self.position[0], self.position[1]
        )
        if abs(diff.x) > 1 or abs(diff.y) > 1:
            return

        self.rotation(COORDS_DIRS[diff])
        self.action_queue.append(Action.STEP_FORWARD)

    def move_to_opponent(self, destination_coords):
        diff = coo.Coords(destination_coords[0], destination_coords[1]) - coo.Coords(
            self.position[0], self.position[1]
        )
        if abs(diff.x) > 1 or abs(diff.y) > 1:
            return
        self.rotation(COORDS_DIRS[diff])
        self.action_queue.append(Action.ATTACK)

    def rotation(self, direction):
        if self.facing == direction:
            return
        diff = coo.Coords(
            DIRS_COORDS[direction][0], DIRS_COORDS[direction][1]
        ) - coo.Coords(DIRS_COORDS[self.facing][0], DIRS_COORDS[self.facing][1])

        if abs(diff.x) == 2 or abs(diff.y) == 2:
            self.action_queue.append(Action.TURN_RIGHT)
            self.action_queue.append(Action.TURN_RIGHT)
        else:
            dirs = list(DIRS_COORDS.keys())
            # this line doesn't work
            diff1 = dirs.index(direction) - dirs.index(self.facing)
            if diff1 == -1 or diff1 == 3:
                self.action_queue.append(Action.TURN_LEFT)
            if diff1 == 1 or diff1 == -3:
                self.action_queue.append(Action.TURN_RIGHT)

    def act_when_blocked(self):
        close_land = self.check_around_for("land")
        # look for land tile around
        if close_land is not None:
            self.move_to(close_land)
            act = self.action_queue[0]
            self.action_queue.pop(0)
            self.prev_facing = self.facing
            self.previous_position = self.position
            self.recommended_path = []
            return act
        else:
            # if no land tile we know of, choose random tile that we don't know anything about
            tile_to_go = random.choice(self.possible_tiles)
            self.move_to(tile_to_go)
            act = self.action_queue[0]
            self.action_queue.pop(0)
            self.prev_facing = self.facing
            self.previous_position = self.position
            self.recommended_path = []
            return act

    def calculate_path(self, destination):
        grid = Grid(matrix=self.map)
        start = grid.node(self.position[0], self.position[1])
        target = grid.node(destination[0], destination[1])

        astar = AStarFinder()
        path, runs = astar.find_path(start, target, grid)
        if len(path) > 1:
            path = path[1:]
            self.recommended_path = path

        elif coo.Coords(destination[0], destination[1]) == self.position:
            if self.position == self.menhir_position:
                self.on_menhir = True
            self.reached_target = True

    def act_update(self):
        act = self.action_queue[0]
        self.action_queue.pop(0)
        self.prev_facing = self.facing
        self.previous_position = self.position
        return act

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.position = knowledge.position
        self.facing = knowledge.visible_tiles[self.position].character.facing.name
        self.knowledge = knowledge
        self.neighbors = self.update_neighbors()
        self.neighbors_types = self.update_neighbors_types()
        self.update_map()
        close_land = self.check_around_for("land")

        if self.mist_positions != []:
            if self.position == self.menhir_position:
                if (
                    self.detect_opponent() != None
                ):  # high priority, we have to defend ourselves
                    opponent_position = self.detect_opponent()
                    self.move_to_opponent(opponent_position)
                    return self.act_update()
                else:
                    return Action.TURN_RIGHT
            if self.store_map_before_mist == None:
                self.store_map_before_mist = self.map

            return self.mist_strategy()

        if self.position == self.weapon_position:
            self.armed = True
            self.weapon_position = None  # make him drop looking for weapon

        if len(self.action_queue) > 0:  # make all the planned moves
            return self.act_update()

        if self.detect_opponent() != None:  # high priority, we have to defend ourselves
            opponent_position = self.detect_opponent()
            self.move_to_opponent(opponent_position)
            return self.act_update()

        if (
            self.recalculate_path
        ):  # if in the map update it turns out that there are obstacles, we have to recalculate the path
            if self.seen_menhir:
                self.calculate_path(self.menhir_position)
                self.follow_path(self.recommended_path)
                self.recalculate_path = False
                return self.act_update()
            elif (
                self.temp_target
            ):  # temp target could be weapon or furthest visible land
                self.calculate_path(self.temp_target)
                self.follow_path(self.recommended_path)
                self.recalculate_path = False
                return self.act_update()

        if (self.prev_facing == self.facing) and (
            self.previous_position == self.position
        ):  # if we didn't move or rotate it means we're blocked
            self.blocked = True
            act = self.act_when_blocked()
            return act

        if (len(self.recommended_path) > 1) and (
            self.seen_menhir and (self.armed == False)
        ):
            if (self.prev_facing == self.facing) and (
                self.previous_position == self.position
            ):
                self.blocked = True
                close_land = self.check_around_for("land")
                act = self.act_when_blocked()
                return act

            # gdy ściezka prawie pusta pojawiają się errory
            else:
                self.follow_path(self.recommended_path)
                return self.act_update()
        if self.menhir_position != None:
            self.calculate_path(self.menhir_position)
            self.seen_menhir = True
            if self.on_menhir:
                return Action.TURN_RIGHT
            self.follow_path(self.recommended_path)
            return self.act_update()
        if self.temp_target:
            """mat = np.logical_not(self.map).astype(int)
            path = astar(
                mat.tolist(),
                (self.position[0], self.position[1]),
                (self.temp_target[0], self.temp_target[1]),
            )"""
            self.calculate_path(self.temp_target)
            if self.position == self.temp_target:
                self.act_when_blocked()
            else:
                self.follow_path(self.recommended_path)
            return self.act_update()

        if close_land != None:
            self.move_to(close_land)
            return self.act_update()
        tile_to_go = random.choice(self.possible_tiles)
        self.move_to(tile_to_go)
        return self.act_update()
        return random.choice(POSSIBLE_ACTIONS)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.position = None
        self.knowledge = None
        self.facing = None
        self.neighbors = []
        self.neighbors_types = dict()
        self.possible_tiles = []
        self.weapon_position = None
        self.menhir_position = None
        self.temp_target = None
        self.action_queue = []
        self.mist_positions = []
        self.recommended_path = []
        self.blocked = False
        self.prev_facing = None
        self.previous_position = None
        self.seen_menhir = False
        self.armed = False
        self.recalculate_path = False
        self.on_menhir = False
        self.reached_target = False
        self.map = np.ones((10, 10))

    @property
    def name(self) -> str:
        return f"AksolotlController{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED


POTENTIAL_CONTROLLERS = [
    AksolotlController("Bob"),
]
