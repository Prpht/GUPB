import random

from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.bi_a_star import BiAStarFinder
from pathfinding.core.grid import Grid

from gupb.model import coordinates as cord
from gupb.model import characters

from .utils import BEST_WEAPONS, ACTIONS, WEAPONS, get_weapon_value
from .mapa import Mapa


class FirstStrategy:

    def __init__(self, mapa: Mapa, weapon_name: str, position: cord.Coords, orientation: characters.Facing) -> None:
        self.mapa = mapa
        self.weapon_name = weapon_name
        self.position = position
        self.orientation = orientation
        self.next_position = None
        self.future_moves = []

        self.weapon_value = get_weapon_value(weapon_name)

        # Flagi sterujace zachowaniem
        self.it_is_time_to_run = False
        self.going_for_potion = False
        self.potion_position_flag = None

    def set_position_and_orientation(self, position, orientation):
        self.orientation = orientation
        self.position = position
        self.next_position = cord.add_coords(self.position, self.orientation.value)

    def set_weapon(self, weapon_name: str) -> None:
        self.weapon_name = weapon_name
        self.weapon_value = get_weapon_value(weapon_name)

    def __enemy_in_front_of_me(self, knowledge: characters.ChampionKnowledge) -> bool:
        if knowledge.visible_tiles[self.next_position].character:
            return True
        return False

    def __can_attack_enemy(self, knowledge: characters.ChampionKnowledge) -> bool:
        return any(
            coord for coord in
            WEAPONS[self.weapon_name].cut_positions(self.mapa.arena.terrain, self.position, self.orientation)
            if coord in knowledge.visible_tiles and knowledge.visible_tiles[coord].character
        )

    @staticmethod
    def __time_to_attack() -> characters.Action:
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
        if self.mapa.mist_position:
            return True
        return False

    def __find_better_weapon(self):
        pass

    def __astar_path(self, destination_x, destination_y):
        grid = Grid(matrix=self.mapa.grid_matrix)
        astar = BiAStarFinder(diagonal_movement=DiagonalMovement.never)
        start = grid.node(self.position.x, self.position.y)
        end = grid.node(destination_x, destination_y)
        path, _ = astar.find_path(start, end, grid)
        return path

    def best_choice(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # Ładujemy łuk
        if self.weapon_value == 4:
            return self.__time_to_attack()

        if self.__can_attack_enemy(knowledge):
            return self.__time_to_attack()

        # Pojawia się mgła, trzeba uciekać.
        if self.__is_mist() and not self.it_is_time_to_run:
            self.it_is_time_to_run = True
            self.future_moves = []

        # Wypiłem miksture można szukać następnej
        if self.potion_position_flag is not None:
            if self.potion_position_flag == self.position:
                self.going_for_potion = False
                self.potion_position_flag = None

        if self.mapa.potion_position is not None and not self.it_is_time_to_run and not self.going_for_potion:
            self.future_moves = []
            self.going_for_potion = True

        if self.future_moves:
            next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)

            if self.position == next_tile:
                self.future_moves.pop(0)
                if self.future_moves:
                    next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)

            sub_tile = cord.sub_coords(next_tile, self.position)
            needed_orientation = characters.Facing(sub_tile)

            if self.orientation == needed_orientation:
                self.future_moves.pop(0)
                return ACTIONS[3]

            else:
                better_turn_left, better_turn_right = self.orientation, self.orientation

                while True:
                    better_turn_left = better_turn_left.turn_left()
                    better_turn_right = better_turn_right.turn_right()

                    if needed_orientation == better_turn_left:
                        return ACTIONS[1]
                    if needed_orientation == better_turn_right:
                        return ACTIONS[2]
        else:
            if self.mapa.menhir_position is not None and self.__is_mist():
                self.future_moves = self.__astar_path(self.mapa.menhir_position[0], self.mapa.menhir_position[1])
            elif self.mapa.potion_position is not None and self.going_for_potion:
                self.future_moves = self.__astar_path(self.mapa.potion_position[0], self.mapa.potion_position[1])
                self.potion_position_flag = cord.Coords(self.future_moves[-1].x, self.future_moves[-1].y)
            else:
                if not self.it_is_time_to_run:
                    not_visited_tile = random.choice(list(self.mapa.not_explored_terrain.keys()))
                    self.future_moves = self.__astar_path(not_visited_tile.x, not_visited_tile.y)
                else:
                    return random.choices(ACTIONS, weights=(0, 1, 1, 4, 0))[0]

        if self.__am_i_blocked(knowledge) and not self.future_moves:
            self.future_moves = []
            return self.__unblock_myself()

        random_move = random.choices(ACTIONS, weights=(0, 1, 1, 4, 0))[0]
        return random_move
