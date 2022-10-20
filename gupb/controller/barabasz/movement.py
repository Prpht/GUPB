from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.model.arenas import ArenaDescription, Arena
from gupb.controller.barabasz.barabasz import weapon_description_to_weapon
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords


class Movement:
    def __init__(self, arena: ArenaDescription):
        self.arena = Arena.load(arena.name)
        self.menhir_coords = None
        self.grid_matrix = self.init_grid_matrix()
        self.starting_weapons = self.get_starting_weapons()

    def get_starting_weapons(self):
        result = {}
        for coords, tile in self.arena.terrain.items():
            if tile.loot is not None:
                description = tile.loot.description()
                result[coords] = weapon_description_to_weapon(description)
        return result

    def is_walkable(self, coords):
        return self.arena.terrain[coords].passable

    def init_grid_matrix(self):
        matrix = [[1 for _ in range(self.arena.size[0])] for _ in range(self.arena.size[1])]
        for coords, tile in self.arena.terrain.items():
            matrix[coords.y][coords.x] = 0 if not self.is_walkable(tile) else 1
        return matrix

    # TODO: Implement info updates
    def update_info(self, knowledge: ChampionKnowledge):
        self.update_menhir(knowledge)
        self.update_weapons(knowledge)

    def update_menhir(self, knowledge: ChampionKnowledge):
        pass

    def update_weapons(self, knowledge: ChampionKnowledge):
        pass

    def find_path(self, start: Coords, end: Coords):
        grid = Grid(matrix=self.grid_matrix)
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        start = grid.node(start.x, start.y)
        end = grid.node(end.x, end.y)
        path, _ = finder.find_path(start, end, grid)
        return path[1:]
