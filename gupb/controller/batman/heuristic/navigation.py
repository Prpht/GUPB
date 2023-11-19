from typing import Optional, Iterator
import numpy as np

from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.bi_a_star import BiAStarFinder

from gupb.model.characters import Action, Facing
from gupb.model.coordinates import Coords, add_coords, sub_coords
from gupb.controller.batman.knowledge.knowledge import (
    Knowledge,
    ArenaKnowledge,
    ChampionKnowledge,
)


FACING_TO_COORDS = {
    Facing.UP: Coords(0, -1),
    Facing.RIGHT: Coords(1, 0),
    Facing.DOWN: Coords(0, 1),
    Facing.LEFT: Coords(-1, 0),
}

FACING_TURN_LEFT = {
    Facing.UP: Facing.LEFT,
    Facing.RIGHT: Facing.UP,
    Facing.DOWN: Facing.RIGHT,
    Facing.LEFT: Facing.DOWN,
}

FACING_TURN_RIGHT = {
    Facing.UP: Facing.RIGHT,
    Facing.RIGHT: Facing.DOWN,
    Facing.DOWN: Facing.LEFT,
    Facing.LEFT: Facing.UP,
}

FACING_TURN_BACK = {
    Facing.UP: Facing.DOWN,
    Facing.RIGHT: Facing.LEFT,
    Facing.DOWN: Facing.UP,
    Facing.LEFT: Facing.RIGHT,
}


class Navigation:
    def __init__(self, knowledge: Knowledge):
        self.knowledge = knowledge

        arena = knowledge.arena.arena
        terrain = arena.terrain

        # TODO update to Graph, so we count in, that turning takes the whole step
        # TODO each cell would have 4 nodes, depending on the direction you are facing
        self.grid_matrix = self.base_grid()

        self.finder = BiAStarFinder(diagonal_movement=DiagonalMovement.never)

    def base_grid(self) -> np.ndarray:
        size = self.knowledge.arena.arena.size
        terrain = self.knowledge.arena.arena.terrain
        grid = np.zeros(size, dtype=np.int32)

        for x, y in np.ndindex(size):
            coords = Coords(x, y)
            grid[y, x] = 1 if terrain[coords].terrain_passable() else 0

        return grid

    def manhattan_distance(self, start: Coords, end: Coords) -> int:
        return abs(start.x - end.x) + abs(start.y - end.y)

    def manhattan_terrain_distance(self, start: Coords, end: Coords) -> int:
        path = self.find_path(start, end)
        return len(path) - 1

    def find_path(self, start: Coords, end: Coords, grid: Grid = None) -> list[Coords]:
        grid = Grid(matrix=self.grid_matrix) if grid is None else Grid(matrix=grid)
        start = grid.node(start.x, start.y)
        end = grid.node(end.x, end.y)

        path, _ = self.finder.find_path(start, end, grid)

        return [Coords(x, y) for x, y in path]

    def front_tile(self, position: Coords, facing: Facing) -> Coords:
        return add_coords(position, FACING_TO_COORDS[facing])

    def right_tile(self, position: Coords, facing: Facing) -> Coords:
        return add_coords(position, FACING_TO_COORDS[FACING_TURN_RIGHT[facing]])

    def left_tile(self, position: Coords, facing: Facing) -> Coords:
        return add_coords(position, FACING_TO_COORDS[FACING_TURN_LEFT[facing]])

    def back_tile(self, position: Coords, facing: Facing) -> Coords:
        return add_coords(position, FACING_TO_COORDS[FACING_TURN_BACK[facing]])

    def is_passable_tile(self, position: Coords) -> bool:
        terrain_tile = self.knowledge.arena.arena.terrain.get(position, None)
        return terrain_tile.terrain_passable() if terrain_tile is not None else False

    def is_free_tile(self, position: Coords) -> bool:
        tile_knowledge = self.knowledge.arena.explored_map.get(position)
        if tile_knowledge is None:
            return False
        return tile_knowledge.passable and tile_knowledge.character is None

    def is_corner_tile(self, position: Coords) -> bool:
        facing = Facing.UP
        passable_tiles = sum(
            [
                self.is_passable_tile(self.front_tile(position, facing)),
                self.is_passable_tile(self.right_tile(position, facing)),
                self.is_passable_tile(self.left_tile(position, facing)),
                self.is_passable_tile(self.back_tile(position, facing)),
            ]
        )
        return passable_tiles <= 2

    def find_closest_free_tile(self, knowledge: Knowledge) -> Coords:
        facing = knowledge.champion.facing
        position = knowledge.position

        if self.is_free_tile(self.front_tile(position, facing)):
            return self.front_tile(position, facing)
        if self.is_free_tile(self.right_tile(position, facing)):
            return self.right_tile(position, facing)
        if self.is_free_tile(self.left_tile(position, facing)):
            return self.left_tile(position, facing)
        else:
            return self.back_tile(position, facing)

    def iterate_tiles_in_region_boundary(
        self, lower_left: Coords, upper_right: Coords
    ) -> Iterator[Coords]:
        for x in range(lower_left.x, upper_right.x + 1):
            yield Coords(x, lower_left.y)
            yield Coords(x, upper_right.y)

        # this does not have corners
        for y in range(lower_left.y + 1, upper_right.y):
            yield Coords(lower_left.x, y)
            yield Coords(upper_right.x, y)

    def path_cost(self, path: list[Coords], grid: np.ndarray) -> int:
        cost = 0
        for coords in path:
            cost += grid[coords.y, coords.x]
        return cost

    def find_nearest_safe_tile(
        self, knowledge: Knowledge, danger_grid: np.ndarray, distance: int = 2
    ) -> Coords:
        delta = Coords(distance, distance)
        tiles2path_danger = dict()
        for candidate_tile in self.iterate_tiles_in_region_boundary(
            sub_coords(knowledge.position, delta), add_coords(knowledge.position, delta)
        ):
            if not self.is_passable_tile(candidate_tile):
                continue

            path = self.find_path(knowledge.position, candidate_tile, danger_grid)
            if not path or len(path) == 1:
                continue

            path_danger = self.path_cost(path, danger_grid)
            tiles2path_danger[candidate_tile] = path_danger

        if not tiles2path_danger:
            if distance < 4:
                return self.find_nearest_safe_tile(knowledge, danger_grid, distance + 1)
            else:
                return self.find_closest_free_tile(knowledge)

        best_tile = min(tiles2path_danger, key=tiles2path_danger.get)
        return best_tile

    def is_headed_towards(self, champion: ChampionKnowledge, position: Coords) -> bool:
        distance = self.manhattan_terrain_distance(champion.position, position)
        next_tile = add_coords(champion.position, FACING_TO_COORDS[champion.facing])
        return self.manhattan_terrain_distance(next_tile, position) <= distance

    def direction_to(self, start: Coords, end: Coords) -> Facing:
        """
        Returns direction in which you have to move to get from start to end

        It works using the y = x, y = -x lines as boundaries for the 4 directions

        :param start: starting point
        :param end: ending point
        :return: direction in which you have to move to get from start to end
        """

        end = sub_coords(end, start)  # point with respect to the origin (0, 0)
        x, y = end.x, end.y
        if x >= y and x > -y:
            return Facing.RIGHT
        if x > y and x <= -y:
            return Facing.UP
        if x <= y and x < -y:
            return Facing.LEFT
        return Facing.DOWN

    def turn(
        self, current_direction: Facing, target_direction: Facing
    ) -> Optional[Action]:
        if current_direction == target_direction:
            return None

        if current_direction == Facing.UP:
            if target_direction in [Facing.RIGHT, Facing.DOWN]:
                return Action.TURN_RIGHT
            else:
                return Action.TURN_LEFT
        elif current_direction == Facing.RIGHT:
            if target_direction in [Facing.DOWN, Facing.LEFT]:
                return Action.TURN_RIGHT
            else:
                return Action.TURN_LEFT
        elif current_direction == Facing.DOWN:
            if target_direction in [Facing.LEFT, Facing.UP]:
                return Action.TURN_RIGHT
            else:
                return Action.TURN_LEFT
        else:  # facing == Facing.LEFT
            if target_direction in [Facing.UP, Facing.RIGHT]:
                return Action.TURN_RIGHT
            else:
                return Action.TURN_LEFT

    def next_step(
        self, knowledge: Knowledge, target: Coords, grid: Grid = None
    ) -> Action:
        path = self.find_path(knowledge.position, target, grid=grid)

        # find_path returns the start and end point as well
        if len(path) == 0 or len(path) == 1:
            return Action.DO_NOTHING

        current_coord = knowledge.position
        next_coord = path[1]

        facing = knowledge.champion.facing
        should_be_facing = self.direction_to(current_coord, next_coord)

        turn_action = self.turn(facing, should_be_facing)

        if turn_action is None:
            return Action.STEP_FORWARD

        return turn_action

    def next_fastest_step(
        self, knowledge: Knowledge, target: Coords, grid: Grid = None
    ) -> Action:
        path = self.find_path(knowledge.position, target, grid=grid)

        # find_path returns the start and end point as well
        if len(path) == 0 or len(path) == 1:
            return Action.DO_NOTHING

        current_coord = knowledge.position
        next_coord = path[1]

        facing = knowledge.champion.facing
        should_be_facing = self.direction_to(current_coord, next_coord)

        if facing == should_be_facing:
            return Action.STEP_FORWARD

        if FACING_TURN_LEFT.get(facing) == should_be_facing:
            return Action.STEP_LEFT

        if FACING_TURN_RIGHT.get(facing) == should_be_facing:
            return Action.STEP_RIGHT

        return Action.STEP_BACKWARD
