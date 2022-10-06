from gupb.model import arenas, coordinates
from typing import List
from pathfinding.core.grid import Grid
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
from gupb.model.characters import Facing
from gupb.model import characters

ArenaMatrix = List[List[bool]]

TURN_ACTIONS = {
    (Facing.UP, Facing.RIGHT): characters.Action.TURN_RIGHT,
    (Facing.UP, Facing.DOWN): characters.Action.TURN_RIGHT,
    (Facing.UP, Facing.LEFT): characters.Action.TURN_LEFT,
    (Facing.RIGHT, Facing.UP): characters.Action.TURN_LEFT,
    (Facing.RIGHT, Facing.DOWN): characters.Action.TURN_RIGHT,
    (Facing.RIGHT, Facing.LEFT): characters.Action.TURN_RIGHT,
    (Facing.DOWN, Facing.UP): characters.Action.TURN_LEFT,
    (Facing.DOWN, Facing.RIGHT): characters.Action.TURN_LEFT,
    (Facing.DOWN, Facing.LEFT): characters.Action.TURN_RIGHT,
    (Facing.LEFT, Facing.UP): characters.Action.TURN_RIGHT,
    (Facing.LEFT, Facing.RIGHT): characters.Action.TURN_RIGHT,
    (Facing.LEFT, Facing.DOWN): characters.Action.TURN_LEFT
} 

class ArenaKnowledge():
    def __init__(self, arena_description: arenas.ArenaDescription):
        self.arena_matrix = self._create_arena_matrix(arena_description.name)
        self.grid = Grid(matrix=self.arena_matrix)
        self.finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        

    @staticmethod
    def _create_arena_matrix(arena_description: arenas.ArenaDescription) -> ArenaMatrix:
        arena = arenas.Arena.load(arena_description)
        arena_matrix = [[1]*arena.size[0]]*arena.size[1]
        for cords, tile in arena.terrain.items():
            arena_matrix[cords.x][cords.y] = 0 if tile.description().type in ['wall', 'sea'] else 1
            arena_matrix[cords.x][cords.y] = 0 if tile.loot else 1
        return arena_matrix
    
    def find_path(self, start: coordinates.Coords, end: coordinates.Coords) -> List[coordinates.Coords]:
        start = self.grid.node(start.x, start.y)
        end = self.grid.node(end.x, end.y)
        path, _ = self.finder.find_path(start, end, self.grid)
        print("finding path!")
        return path[1:]

    def get_desired_facing(self, current_position: coordinates.Coords, desired_position: coordinates.Coords) -> Facing:
        dx = current_position.x - desired_position.x
        dy = current_position.y - desired_position.y

        desired_facing_coordinates = coordinates.Coords(dx,dy)

        return Facing(desired_facing_coordinates)
        
        
    def determine_action(self, current_facing : Facing, desired_facing : Facing) -> characters.Action:
        if current_facing == desired_facing:
            return characters.Action.STEP_FORWARD
        return TURN_ACTIONS[(current_facing, desired_facing)]
    
    def get_facing(self, knowledge: characters.ChampionKnowledge) -> Facing:
        tile = knowledge.visible_tiles.get(knowledge.position)
        return tile.character.facing


        
