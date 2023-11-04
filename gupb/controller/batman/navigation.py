import numpy as np

from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.bi_a_star import BiAStarFinder

from gupb.model.characters import Action, Facing
from gupb.model.coordinates import Coords, add_coords
from gupb.controller.batman.environment.knowledge import Knowledge, ArenaKnowledge


FACING_TO_COORDS = {
    Facing.UP:    Coords( 0, -1),
    Facing.RIGHT: Coords( 1,  0),
    Facing.DOWN:  Coords( 0,  1),
    Facing.LEFT:  Coords(-1,  0),
}

FACING_TURN_LEFT = {
    Facing.UP:    Facing.LEFT,
    Facing.RIGHT: Facing.UP,
    Facing.DOWN:  Facing.RIGHT,
    Facing.LEFT:  Facing.DOWN,
}

FACING_TURN_RIGHT = {
    Facing.UP:    Facing.RIGHT,
    Facing.RIGHT: Facing.DOWN,
    Facing.DOWN:  Facing.LEFT,
    Facing.LEFT:  Facing.UP,
}

FACING_TURN_BACK = {
    Facing.UP:    Facing.DOWN,
    Facing.RIGHT: Facing.LEFT,
    Facing.DOWN:  Facing.UP,
    Facing.LEFT:  Facing.RIGHT,
}


class Navigation:
    def __init__(self, knowledge: Knowledge):
        self.knowledge = knowledge

        arena = knowledge.arena.arena
        terrain = arena.terrain

        # TODO update to Graph, so we count in, that turning takes the whole step
        # TODO each cell would have 4 nodes, depending on the direction you are facing
        size = arena.size
        grid = np.zeros(size, dtype=np.int32)

        for x, y in np.ndindex(size):
            coords = Coords(x, y)
            grid[y, x] = 1 if terrain[coords].terrain_passable() else 0

        self.grid_matrix = grid

        self.finder = BiAStarFinder(diagonal_movement=DiagonalMovement.never)

    def manhattan_distance(self, start: Coords, end: Coords) -> int:
        return abs(start.x - end.x) + abs(start.y - end.y)

    def manhattan_terrain_distance(self, start: Coords, end: Coords) -> int:
        path = self.find_path(start, end)
        return len(path) - 1

    def find_path(self, start: Coords, end: Coords) -> list[Coords]:
        grid = Grid(matrix=self.grid_matrix)
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

    def is_free_tile(self, position: Coords) -> bool:
        tile_knowledge = self.knowledge.arena.explored_map.get(position)
        if tile_knowledge is None:
            return False
        return tile_knowledge.passable and tile_knowledge.character is None

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

    def direction_to(self, start: Coords, end: Coords) -> Facing:
        if start.x < end.x:
            return Facing.RIGHT
        elif start.x > end.x:
            return Facing.LEFT
        elif start.y < end.y:
            return Facing.DOWN
        return Facing.UP

    def next_step(self, knowledge: Knowledge, target: Coords) -> Action:
        path = self.find_path(knowledge.position, target)

        # find_path returns the start and end point as well
        if len(path) == 0 or len(path) == 1:
            return Action.DO_NOTHING

        current_coord = knowledge.position
        next_coord = path[1]

        facing = knowledge.champion.facing
        should_be_facing = self.direction_to(current_coord, next_coord)

        if facing == should_be_facing:
            return Action.STEP_FORWARD

        if facing == Facing.UP:
            if should_be_facing in [Facing.RIGHT, Facing.DOWN]:
                return Action.TURN_RIGHT
            else:
                return Action.TURN_LEFT
        elif facing == Facing.RIGHT:
            if should_be_facing in [Facing.DOWN, Facing.LEFT]:
                return Action.TURN_RIGHT
            else:
                return Action.TURN_LEFT
        elif facing == Facing.DOWN:
            if should_be_facing in [Facing.LEFT, Facing.UP]:
                return Action.TURN_RIGHT
            else:
                return Action.TURN_LEFT
        else:  # facing == Facing.LEFT
            if should_be_facing in [Facing.UP, Facing.RIGHT]:
                return Action.TURN_RIGHT
            else:
                return Action.TURN_LEFT
