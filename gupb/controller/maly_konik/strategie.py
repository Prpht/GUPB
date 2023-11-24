import random
import numpy as np

from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.grid import Grid

from gupb.model import coordinates as cord
from gupb.model import characters

from .utils import BEST_WEAPONS, ACTIONS, WEAPONS, get_weapon_value
from .mapa import Mapa


class FirstStrategy:

    def __init__(self,
                 mapa: Mapa,
                 weapon_name: str,
                 position: cord.Coords,
                 orientation: characters.Facing,
                 health: int) -> None:
        self.mapa = mapa
        self.weapon_name = weapon_name
        self.position = position
        self.orientation = orientation
        self.next_position = None
        self.future_moves = []
        self.health = health

        self.weapon_value = get_weapon_value(weapon_name)

        # Flagi sterujace zachowaniem
        self.it_is_time_to_run = False
        self.going_for_potion = False
        self.potion_position_flag = None
        self.step_back = False

    def set_position_and_orientation(self, position, orientation):
        self.orientation = orientation
        self.position = position
        self.next_position = cord.add_coords(self.position, self.orientation.value)

    def set_weapon(self, weapon_name: str) -> None:
        self.weapon_name = weapon_name
        self.weapon_value = get_weapon_value(weapon_name)

    def reset_moves(self) -> None:
        self.future_moves = []

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

    def __can_enemy_attack(self, pos) -> bool:
        danger_zone = WEAPONS[self.mapa.enemy.weapon.name].cut_positions(
            self.mapa.arena.terrain,
            cord.Coords(*self.mapa.closest_enemy_cord),
            self.mapa.enemy[3]
        )
        return any(cor == pos for cor in danger_zone)

    def should_attack(self, knowledge: characters.ChampionKnowledge) -> bool:
        if self.__can_attack_enemy(knowledge) and not self.__can_enemy_attack(self.position):
            return True

        if self.health <= self.mapa.enemy.health:
            return False

        if BEST_WEAPONS[self.mapa.enemy.weapon.name] >= BEST_WEAPONS[self.weapon_name] and self.__enemy_in_front_of_me(
                knowledge):
            return True

        return False

    @staticmethod
    def __time_to_attack() -> characters.Action:
        return ACTIONS[0]

    @staticmethod
    def __unblock_myself() -> characters.Action:
        return random.choices(ACTIONS, weights=(0, 0, 2, 0, 0, 1))[0]

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
        astar = AStarFinder(diagonal_movement=DiagonalMovement.never)
        start = grid.node(self.position.x, self.position.y)
        end = grid.node(destination_x, destination_y)
        path, _ = astar.find_path(start, end, grid)
        return path

    def __run_away(self):
        # print("UCIEKAM")

        # not_visited_tiles = list(self.mapa.not_explored_terrain.keys())
        #
        # if len(not_visited_tiles) > 0:
        #     for not_visited_tile in not_visited_tiles:
        #         x = not_visited_tile.x
        #         y = not_visited_tile.y
        #         if not self.__can_enemy_attack(cord.Coords(x, y)):
        #             print(f"Tutaj wróg nie zaatakuj: {x,y}")
        #             self.future_moves = self.__astar_path(x, y)
        #             if self.future_moves[0].x != self.mapa.closest_enemy_cord[0] and self.future_moves[0].y != \
        #                     self.mapa.closest_enemy_cord[1]:
        #                 break

        # else:
        flag = True
        iteration = 0
        randomly_selected_cor = (0, 0)
        self.step_back = False

        while flag:
            iteration += 1
            if iteration >= 100:
                # print('Krok w tyl')
                flag = False
                self.future_moves = []
                self.step_back = True
                break

            indices = np.argwhere(self.mapa.grid_matrix == 1)
            random_index = np.random.choice(len(indices))
            randomly_selected_cor = tuple(indices[random_index])

            if randomly_selected_cor[0] != self.position[0] and randomly_selected_cor[1] != self.position[1]:
                self.future_moves = self.__astar_path(randomly_selected_cor[0], randomly_selected_cor[1])

                if len(self.future_moves) >= 5:

                    if self.future_moves[0].x == self.position[0] and self.future_moves[0].y == self.position[1]:
                        self.future_moves.pop(0)

                    if self.future_moves[0].x != self.mapa.closest_enemy_cord[0] and self.future_moves[0].y != \
                            self.mapa.closest_enemy_cord[1]:
                        flag = False

        if self.future_moves[0].x == self.position[0] and self.future_moves[0].y == self.position[1]:
            self.future_moves.pop(0)

    def best_choice(self, knowledge: characters.ChampionKnowledge) -> characters.Action:

        if self.mapa.menhir_position is not None:
            if self.position[0] == self.mapa.menhir_position[0] and self.position[1] == self.mapa.menhir_position[1]:
                self.it_is_time_to_run = False
            if self.position[0] == self.mapa.menhir_position[0] and self.position[1] == self.mapa.menhir_position[1] and self.__is_mist():
                if self.__can_attack_enemy(knowledge):
                    return self.__time_to_attack()
                else:
                    self.future_moves = []
                    random_move = random.choices(ACTIONS, weights=(0, 2, 2, 1, 0, 1))[0]
                    return random_move

        if self.__enemy_in_front_of_me(knowledge) and not self.__can_attack_enemy(knowledge) and not self.it_is_time_to_run:
            self.__run_away()
            if self.step_back:
                self.step_back = False
                return ACTIONS[-1]

        elif self.__enemy_in_front_of_me(knowledge) and not self.__can_enemy_attack(knowledge) and self.it_is_time_to_run:
            return self.__time_to_attack()

        # Pojawia się mgła, trzeba uciekać.
        if self.__is_mist() and not self.it_is_time_to_run:
            self.it_is_time_to_run = True
            self.future_moves = []

        # Ładujemy łuk
        if self.weapon_value == 4:
            return self.__time_to_attack()

        if self.mapa.enemy is not None:  # and not self.it_is_time_to_run:
            if self.__can_attack_enemy(knowledge) and self.should_attack(knowledge):
                return self.__time_to_attack()

            # Warto zaatakować ale nie mamy dobrej pozycji
            if self.should_attack(knowledge) and not self.__can_attack_enemy(knowledge):
                pass

            if self.__enemy_in_front_of_me(knowledge) and not self.should_attack(knowledge) and not self.it_is_time_to_run:
                # print("Mam wroga ale nie powinienem go atakować")
                self.__run_away()
                if self.step_back:
                    self.step_back = False
                    return ACTIONS[-1]

        # if self.__can_attack_enemy(knowledge):
        #     return self.__time_to_attack()

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

            if self.position[0] == next_tile.x and self.position[1] == next_tile.y:
                self.future_moves.pop(0)
                if self.future_moves:
                    next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)
                else:
                    flag = True
                    randomly_selected_cor = (0, 0)

                    while flag:
                        indices = np.argwhere(self.mapa.grid_matrix == 1)
                        random_index = np.random.choice(len(indices))
                        randomly_selected_cor = tuple(indices[random_index])

                        if randomly_selected_cor[0] != self.position[0] and randomly_selected_cor[1] != self.position[
                            1]:
                            self.future_moves = self.__astar_path(randomly_selected_cor[0], randomly_selected_cor[1])
                            if len(self.future_moves) >= 4:
                                flag = False

                    next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)

                    if self.position[0] == next_tile.x and self.position[1] == next_tile.y:
                        self.future_moves.pop(0)
                        next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)

            sub_tile = cord.sub_coords(next_tile, self.position)

            if sub_tile.x == 0 and sub_tile.y == 0:
                try:
                    self.future_moves.pop(0)
                    next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)
                    sub_tile = cord.sub_coords(next_tile, self.position)
                except IndexError:
                    self.future_moves = []
                    random_move = random.choices(ACTIONS, weights=(0, 1, 1, 2, 0, 4))[0]
                    return random_move

            if abs(sub_tile.x) + abs(sub_tile.y) > 1:
                self.future_moves = []
                random_move = random.choices(ACTIONS, weights=(0, 1, 1, 2, 0, 4))[0]
                return random_move

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
                    try:
                        not_visited_tile = random.choice(list(self.mapa.not_explored_terrain.keys()))
                        self.future_moves = self.__astar_path(not_visited_tile.x, not_visited_tile.y)
                    except IndexError:
                        self.future_moves = []
                        return random.choices(ACTIONS, weights=(0, 1, 1, 4, 0, 1))[0]
                else:
                    self.future_moves = []
                    return random.choices(ACTIONS, weights=(0, 1, 1, 4, 0, 1))[0]

        if self.__am_i_blocked(knowledge) and not self.future_moves:
            self.future_moves = []
            return self.__unblock_myself()

# import random
# import numpy as np
#
# from pathfinding.core.diagonal_movement import DiagonalMovement
# from pathfinding.finder.bi_a_star import BiAStarFinder
# from pathfinding.finder.a_star import AStarFinder
# from pathfinding.core.grid import Grid
#
# from gupb.model import coordinates as cord
# from gupb.model import characters
#
# from .utils import BEST_WEAPONS, ACTIONS, WEAPONS, get_weapon_value
# from .mapa import Mapa
#
#
# class FirstStrategy:
#
#     def __init__(self, mapa: Mapa, weapon_name: str, position: cord.Coords, orientation: characters.Facing, health) -> None:
#         self.mapa = mapa
#         self.weapon_name = weapon_name
#         self.position = position
#         self.orientation = orientation
#         self.next_position = None
#         self.future_moves = []
#
#         self.weapon_value = get_weapon_value(weapon_name)
#
#         # Flagi sterujace zachowaniem
#         self.it_is_time_to_run = False
#         self.going_for_potion = False
#         self.potion_position_flag = None
#
#     def set_position_and_orientation(self, position, orientation):
#         self.orientation = orientation
#         self.position = position
#         self.next_position = cord.add_coords(self.position, self.orientation.value)
#
#     def set_weapon(self, weapon_name: str) -> None:
#         self.weapon_name = weapon_name
#         self.weapon_value = get_weapon_value(weapon_name)
#
#     def __enemy_in_front_of_me(self, knowledge: characters.ChampionKnowledge) -> bool:
#         if knowledge.visible_tiles[self.next_position].character:
#             return True
#         return False
#
#     def __can_attack_enemy(self, knowledge: characters.ChampionKnowledge) -> bool:
#         return any(
#             coord for coord in
#             WEAPONS[self.weapon_name].cut_positions(self.mapa.arena.terrain, self.position, self.orientation)
#             if coord in knowledge.visible_tiles and knowledge.visible_tiles[coord].character
#         )
#
#     @staticmethod
#     def __time_to_attack() -> characters.Action:
#         return ACTIONS[0]
#
#     @staticmethod
#     def __unblock_myself() -> characters.Action:
#         return random.choices(ACTIONS, weights=(0, 0, 1, 0, 0))[0]
#
#     def __am_i_blocked(self, knowledge: characters.ChampionKnowledge) -> bool:
#         if self.next_position in knowledge.visible_tiles.keys():
#             type_of_next_tile = knowledge.visible_tiles[self.next_position].type
#             if type_of_next_tile == 'wall' or type_of_next_tile == 'sea':
#                 return True
#         return False
#
#     def __is_mist(self) -> bool:
#         if self.mapa.mist_position:
#             return True
#         return False
#
#     def __find_better_weapon(self):
#         pass
#
#     def __astar_path(self, destination_x, destination_y):
#         grid = Grid(matrix=self.mapa.grid_matrix)
#         astar = BiAStarFinder(diagonal_movement=DiagonalMovement.never)
#         start = grid.node(self.position.x, self.position.y)
#         end = grid.node(destination_x, destination_y)
#         path, _ = astar.find_path(start, end, grid)
#         return path
#
#     def best_choice(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
#         # Ładujemy łuk
#         if self.weapon_value == 4:
#             return self.__time_to_attack()
#
#         if self.__can_attack_enemy(knowledge):
#             return self.__time_to_attack()
#
#         # Pojawia się mgła, trzeba uciekać.
#         if self.__is_mist() and not self.it_is_time_to_run:
#             self.it_is_time_to_run = True
#             self.future_moves = []
#
#         # Wypiłem miksture można szukać następnej
#         if self.potion_position_flag is not None:
#             if self.potion_position_flag == self.position:
#                 self.going_for_potion = False
#                 self.potion_position_flag = None
#
#         if self.mapa.potion_position is not None and not self.it_is_time_to_run and not self.going_for_potion:
#             self.future_moves = []
#             self.going_for_potion = True
#
#         if self.future_moves:
#             next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)
#
#             if self.position[0] == next_tile.x and self.position[1] == next_tile.y:
#                 self.future_moves.pop(0)
#                 if self.future_moves:
#                     next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)
#                 else:
#                     flag = True
#                     randomly_selected_cor = (0, 0)
#
#                     while flag:
#                         indices = np.argwhere(self.mapa.grid_matrix == 1)
#                         random_index = np.random.choice(len(indices))
#                         randomly_selected_cor = tuple(indices[random_index])
#
#                         if randomly_selected_cor[0] != self.position[0] and randomly_selected_cor[1] != self.position[1]:
#                             self.future_moves = self.__astar_path(randomly_selected_cor[0], randomly_selected_cor[1])
#                             if len(self.future_moves) >= 4:
#                                 flag = False
#
#                     next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)
#
#                     if self.position[0] == next_tile.x and self.position[1] == next_tile.y:
#                         self.future_moves.pop(0)
#                         next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)
#
#             sub_tile = cord.sub_coords(next_tile, self.position)
#
#             if sub_tile.x == 0 and sub_tile.y == 0:
#                 try:
#                     self.future_moves.pop(0)
#                     next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)
#                     sub_tile = cord.sub_coords(next_tile, self.position)
#                 except IndexError:
#                     self.future_moves = []
#                     random_move = random.choices(ACTIONS, weights=(0, 1, 1, 2, 0, 4))[0]
#                     return random_move
#
#             if abs(sub_tile.x) + abs(sub_tile.y) > 1:
#                 self.future_moves = []
#                 random_move = random.choices(ACTIONS, weights=(0, 1, 1, 2, 0, 4))[0]
#                 return random_move
#
#             needed_orientation = characters.Facing(sub_tile)
#
#             if self.orientation == needed_orientation:
#                 self.future_moves.pop(0)
#                 return ACTIONS[3]
#
#             else:
#                 better_turn_left, better_turn_right = self.orientation, self.orientation
#
#                 while True:
#                     better_turn_left = better_turn_left.turn_left()
#                     better_turn_right = better_turn_right.turn_right()
#
#                     if needed_orientation == better_turn_left:
#                         return ACTIONS[1]
#                     if needed_orientation == better_turn_right:
#                         return ACTIONS[2]
#         else:
#             if self.mapa.menhir_position is not None and self.__is_mist():
#                 self.future_moves = self.__astar_path(self.mapa.menhir_position[0], self.mapa.menhir_position[1])
#             elif self.mapa.potion_position is not None and self.going_for_potion:
#                 self.future_moves = self.__astar_path(self.mapa.potion_position[0], self.mapa.potion_position[1])
#                 self.potion_position_flag = cord.Coords(self.future_moves[-1].x, self.future_moves[-1].y)
#             else:
#                 if not self.it_is_time_to_run:
#                     try:
#                         not_visited_tile = random.choice(list(self.mapa.not_explored_terrain.keys()))
#                         self.future_moves = self.__astar_path(not_visited_tile.x, not_visited_tile.y)
#                     except IndexError:
#                         self.future_moves = []
#                         return random.choices(ACTIONS, weights=(0, 1, 1, 4, 0, 1))[0]
#                 else:
#                     self.future_moves = []
#                     return random.choices(ACTIONS, weights=(0, 1, 1, 4, 0, 1))[0]
#
#         if self.__am_i_blocked(knowledge) and not self.future_moves:
#             self.future_moves = []
#             return self.__unblock_myself()
