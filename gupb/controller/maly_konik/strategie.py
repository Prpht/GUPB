import random

from .utils import BEST_WEAPONS, ACTIONS
from .mapa import Mapa
from gupb.model import coordinates as cord
from gupb.model import characters
from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.grid import Grid
from pathfinding.core.diagonal_movement import DiagonalMovement


class FirstStrategy:

    def __init__(self, map: Mapa, weapon_value: int, position: cord.Coords, orientation: characters.Facing) -> None:
        self.map = map
        self.weapon_value = weapon_value
        self.position = position
        self.orientation = orientation
        self.next_position = None
        self.future_moves = []
        self.it_is_time_to_run = False

    def set_position_and_orientation(self, position, orientation):
        self.orientation = orientation
        self.position = position
        self.next_position = cord.add_coords(self.position, self.orientation.value)

    def __enemy_in_front_of_me(self, knowledge: characters.ChampionKnowledge) -> bool:
        if knowledge.visible_tiles[self.next_position].character:
            return True
        return False

    @staticmethod
    def __defending_myself() -> characters.Action:
        return ACTIONS[0]

    @staticmethod
    def __unblock_myself() -> characters.Action:
        return random.choices(ACTIONS, weights=(0, 0, 1, 0, 0))[0]

    def __am_i_blocked(self, knowledge: characters.ChampionKnowledge) -> bool:
        if self.next_position in knowledge.visible_tiles.keys():
            type_of_next_tile = knowledge.visible_tiles[self.next_position].type
            if type_of_next_tile == 'wall' or type_of_next_tile == 'sea':
                return True
        return False

    def __is_mist(self) -> bool:
        if self.map.mist_position:
            return True
        return False

    def __escape_mnist(self):
        pass

    def __find_better_weapon(self):
        pass

    def __astar_path(self, destination_x, destination_y):
        grid = Grid(matrix=self.map.grid_matrix)
        astar = AStarFinder(diagonal_movement=DiagonalMovement.never)
        start = grid.node(self.position.x, self.position.y)
        end = grid.node(destination_x, destination_y)
        path, _ = astar.find_path(start, end, grid)
        if len(path) > 0:
            path.pop(0)
        return path

    def best_choice(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.__enemy_in_front_of_me(knowledge):
            return self.__defending_myself()

        # Pojawia się mgła, trzeba uciekać.
        if self.__is_mist() and not self.it_is_time_to_run:
            self.it_is_time_to_run = True
            self.future_moves = []

        if self.future_moves:
            next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)

            # To nie powinno się zdarzyć ale tak na wszelki
            if self.position == next_tile:
                self.future_moves.pop(0)

            sub_tile = cord.sub_coords(next_tile, self.position)
            if sub_tile.x != 0 and sub_tile.y != 0:
                self.future_moves = []
                return random.choices(ACTIONS, weights=(0, 1, 1, 4, 0))[0]
            if abs(sub_tile.x) > 1 or abs(sub_tile.y) > 1:
                self.future_moves = []
                return random.choices(ACTIONS, weights=(0, 1, 1, 4, 0))[0]
            needed_orientation = characters.Facing(sub_tile)

            # print("next", next_tile)
            # print("position", self.position)
            # print("orientation", self.orientation)
            # print("sub", sub_tile)
            # print("ned_or", needed_orientation)

            if self.orientation == needed_orientation:
                self.future_moves.pop(0)
                return ACTIONS[3]  # krok do przodu

            else:
                if (self.orientation == characters.Facing.UP and needed_orientation == characters.Facing.LEFT) \
                        or (self.orientation == characters.Facing.RIGHT and needed_orientation == characters.Facing.UP) \
                        or (self.orientation == characters.Facing.DOWN and needed_orientation == characters.Facing.UP) \
                        or (
                        self.orientation == characters.Facing.LEFT and needed_orientation == characters.Facing.DOWN):
                    return ACTIONS[1]

                return ACTIONS[2]
        else:
            if self.map.menhir_position is not None and self.__is_mist():
                self.future_moves = self.__astar_path(self.map.menhir_position[0], self.map.menhir_position[1])
            else:
                if not self.it_is_time_to_run:
                    not_visited_tile = random.choice(list(self.map.not_explored_terrain.keys()))
                    self.future_moves = self.__astar_path(not_visited_tile.x, not_visited_tile.y)
                else:
                    return random.choices(ACTIONS, weights=(0, 1, 1, 4, 0))[0]

        if self.__am_i_blocked(knowledge):
            self.future_moves = []
            return self.__unblock_myself()

        random_move = random.choices(ACTIONS, weights=(0, 1, 1, 4, 0))[0]
        return random_move
