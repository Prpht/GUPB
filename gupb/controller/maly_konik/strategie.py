import random
import numpy as np

from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.grid import Grid

from gupb.model import coordinates as cord
from gupb.model import characters

from .utils import WORST_WEAPONS, ACTIONS, WEAPONS, get_weapon_value, get_cords_around_point
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
        self.run_from_mist = False
        self.going_for_potion = False
        self.potion_position_flag = None
        self.going_for_weapon = False
        self.weapon_position_flag = None

        self.it_is_time_to_attack = False
        self.it_is_time_to_run = False
        self.go_crazy = False
        self.path_to_run_dont_exist = False

        self.spot_to_attack = None

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
        next_tile = cord.add_coords(self.position, self.orientation.value)  # noqa

        try:
            if knowledge.visible_tiles[next_tile].character:
                return True
        except KeyError:
            pass

        return False

    def __can_attack_enemy(self, knowledge: characters.ChampionKnowledge, position, orientation) -> bool:
        return any(
            coord for coord in
            WEAPONS[self.weapon_name].cut_positions(self.mapa.arena.terrain, position, orientation)
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
        if self.__can_attack_enemy(knowledge, self.position, self.orientation) and not self.__can_enemy_attack(self.position):
            return True

        if self.health < self.mapa.enemy.health:
            return False

        if WORST_WEAPONS[self.mapa.enemy.weapon.name] >= WORST_WEAPONS[self.weapon_name] and self.__can_attack_enemy(knowledge, self.position, self.orientation):
            return True

        if self.health == self.mapa.enemy.health and WORST_WEAPONS[self.mapa.enemy.weapon.name] == WORST_WEAPONS[self.weapon_name]:
            return True

        return False

    @staticmethod
    def __unblock_myself() -> characters.Action:
        return random.choices(ACTIONS, weights=(0, 0, 2, 0, 0, 1))[0]

    @staticmethod
    def __random_moves():
        return random.choices(ACTIONS, weights=(0, 2, 2, 1, 0, 1))[0]

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

    def __go_to_random_cords(self):
        flag = True
        iteration = 0

        while flag:
            iteration += 1
            if iteration >= 100:
                flag = False
                break

            indices = np.argwhere(self.mapa.grid_matrix == 1)
            random_index = np.random.choice(len(indices))
            randomly_selected_cor = tuple(indices[random_index])

            if randomly_selected_cor[0] != self.position[0] and randomly_selected_cor[1] != self.position[1]:
                self.future_moves = self.__astar_path(randomly_selected_cor[0], randomly_selected_cor[1])

                if len(self.future_moves) >= 5:

                    if self.future_moves[0].x == self.position[0] and self.future_moves[0].y == self.position[1]:
                        self.future_moves.pop(0)

                    flag = False

    def __run_away(self):
        flag = True
        iteration = 0

        while flag:
            iteration += 1
            if iteration >= 100:
                # print('Krok w tyl')
                flag = False
                self.future_moves = []
                self.path_to_run_dont_exist = True
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

    def check_my_status(self, knowledge: characters.ChampionKnowledge):
        # Pojawia się mgła, trzeba uciekać.
        if self.__is_mist() and not self.run_from_mist:
            self.run_from_mist = True
            self.reset_moves()

        if self.mapa.menhir_position is not None:
            if self.position[0] == self.mapa.menhir_position[0] and self.position[1] == self.mapa.menhir_position[1]:
                self.run_from_mist = False
            if self.position[0] == self.mapa.menhir_position[0] and self.position[1] == self.mapa.menhir_position[1] and self.__is_mist():
                if self.__can_attack_enemy(knowledge, self.position, self.orientation):
                    self.it_is_time_to_attack = True
                else:
                    self.go_crazy = True
                    self.reset_moves()

        if self.__enemy_in_front_of_me(knowledge) and not self.__can_attack_enemy(knowledge, self.position, self.orientation) and not self.run_from_mist:
            self.it_is_time_to_run = True
            self.reset_moves()

        elif self.__enemy_in_front_of_me(knowledge) and not self.__can_enemy_attack(knowledge) and self.run_from_mist:
            self.it_is_time_to_attack = True

        if self.mapa.enemy is not None:  # and not self.it_is_time_to_run:
            if self.__can_attack_enemy(knowledge, self.position, self.orientation) and self.should_attack(knowledge):
                self.it_is_time_to_attack = True

            # Warto zaatakować ale nie mamy dobrej pozycji
            if self.should_attack(knowledge) and not self.__can_attack_enemy(knowledge, self.position, self.orientation):
                spiral_cords = get_cords_around_point(self.mapa.closest_enemy_cord[0], self.mapa.closest_enemy_cord[1])

                spiral_list = []

                for _ in range(100):
                    spiral_list.append(next(spiral_cords))

                stop_flag = False

                for possible_position in spiral_list:
                    pos = cord.Coords(possible_position[0], possible_position[1])

                    for coord in WEAPONS[self.weapon_name].cut_positions(self.mapa.arena.terrain, pos, characters.Facing.UP):
                        if coord == self.mapa.closest_enemy_cord and self.mapa.grid_matrix[pos.y, pos.x] == 1: # noqa
                            self.spot_to_attack = pos
                            stop_flag = True

                        if stop_flag:
                            break

                    for coord in WEAPONS[self.weapon_name].cut_positions(self.mapa.arena.terrain, pos, characters.Facing.UP):
                        if coord == self.mapa.closest_enemy_cord and self.mapa.grid_matrix[pos.y, pos.x] == 1: # noqa
                            self.spot_to_attack = pos
                            stop_flag = True

                            if stop_flag:
                                break

                    for coord in WEAPONS[self.weapon_name].cut_positions(self.mapa.arena.terrain, pos, characters.Facing.UP):
                        if coord == self.mapa.closest_enemy_cord and self.mapa.grid_matrix[pos.y, pos.x] == 1: # noqa
                            self.spot_to_attack = pos
                            stop_flag = True

                            if stop_flag:
                                break

                    for coord in WEAPONS[self.weapon_name].cut_positions(self.mapa.arena.terrain, pos, characters.Facing.UP):
                        if coord == self.mapa.closest_enemy_cord and self.mapa.grid_matrix[pos.y, pos.x] == 1: # noqa
                            self.spot_to_attack = pos
                            stop_flag = True

                            if stop_flag:
                                break

                    if stop_flag:
                        break

            if self.__enemy_in_front_of_me(knowledge) and not self.should_attack(knowledge) and not self.run_from_mist:
                # print("Mam wroga ale nie powinienem go atakować")
                self.it_is_time_to_run = True
                self.reset_moves()

        # if self.__can_attack_enemy(knowledge):
        #     return self.__time_to_attack()

        # Wypiłem miksture można szukać następnej
        if self.potion_position_flag is not None:
            if self.potion_position_flag == self.position:
                self.going_for_potion = False
                self.potion_position_flag = None

        if self.mapa.potion_position is not None and not self.run_from_mist and not self.going_for_potion:
            self.going_for_potion = True
            self.reset_moves()

        if self.weapon_position_flag is not None:
            if self.weapon_position_flag == self.position:
                self.mapa.weapon_position = None
                self.mapa.weapon_name = None
                self.going_for_weapon = False
                self.weapon_position_flag = None

        if self.mapa.weapon_position is not None and not self.run_from_mist and not self.going_for_weapon and not self.going_for_potion:
            if WORST_WEAPONS[self.mapa.weapon_name] < WORST_WEAPONS[self.weapon_name]:
                self.going_for_weapon = True
                self.reset_moves()

    def plan_my_moves(self):
        if self.it_is_time_to_run:
            self.it_is_time_to_run = False
            self.__run_away()

        if self.mapa.menhir_position is not None and self.__is_mist():
            self.future_moves = self.__astar_path(self.mapa.menhir_position[0], self.mapa.menhir_position[1])
        elif self.mapa.potion_position is not None and self.going_for_potion:
            self.future_moves = self.__astar_path(self.mapa.potion_position[0], self.mapa.potion_position[1])
            self.potion_position_flag = cord.Coords(self.future_moves[-1].x, self.future_moves[-1].y)
        elif self.mapa.weapon_position is not None and self.going_for_weapon:
            self.future_moves = self.__astar_path(self.mapa.weapon_position[0], self.mapa.weapon_position[1])
            self.weapon_position_flag = cord.Coords(self.future_moves[-1].x, self.future_moves[-1].y)
        elif self.spot_to_attack is not None:
            self.future_moves = self.__astar_path(self.spot_to_attack.x, self.spot_to_attack.y)
            self.spot_to_attack = None
        else:
            if not self.run_from_mist:
                try:
                    not_visited_tile = random.choice(list(self.mapa.not_explored_terrain.keys()))
                    self.future_moves = self.__astar_path(not_visited_tile.x, not_visited_tile.y)
                except IndexError:
                    self.__go_to_random_cords()
            else:
                # TODO mehchanika uciekania gdy nie ma menhira
                try:
                    not_visited_tile = random.choice(list(self.mapa.not_explored_terrain.keys()))
                    self.future_moves = self.__astar_path(not_visited_tile.x, not_visited_tile.y)
                except IndexError:
                    self.__go_to_random_cords()

    def move(self, knowledge: characters.ChampionKnowledge):
        if self.path_to_run_dont_exist:
            self.path_to_run_dont_exist = False
            self.__random_moves()

        if self.it_is_time_to_attack:
            self.it_is_time_to_attack = False
            return ACTIONS[0]

        if self.go_crazy:
            self.go_crazy = False
            self.__random_moves()

        # Ładujemy łuk
        # TODO rozważyć czy warto atakować kosztem ruchu
        # if self.weapon_value == 4:
        #     return ACTIONS[0]

        next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)

        if self.position[0] == next_tile.x and self.position[1] == next_tile.y:
            self.future_moves.pop(0)
            if self.future_moves:
                next_tile = cord.Coords(self.future_moves[0].x, self.future_moves[0].y)
            else:
                self.__go_to_random_cords()

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
            if not self.__enemy_in_front_of_me(knowledge):
                self.future_moves.pop(0)
                return ACTIONS[3]
            else:
                self.__run_away()
                return ACTIONS[0]

        else:
            better_turn_left, better_turn_right = self.orientation, self.orientation

            while True:
                better_turn_left = better_turn_left.turn_left()
                better_turn_right = better_turn_right.turn_right()

                if needed_orientation == better_turn_left:
                    return ACTIONS[1]
                if needed_orientation == better_turn_right:
                    return ACTIONS[2]
