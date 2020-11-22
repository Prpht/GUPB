from enum import Enum
from queue import SimpleQueue
import random
from typing import Dict, Type, Optional, Tuple, List, Set
import numpy as np

from gupb.model import arenas, coordinates, weapons, tiles, characters, games

FACING_ORDER = [characters.Facing.LEFT, characters.Facing.UP, characters.Facing.RIGHT, characters.Facing.DOWN]

ALPHA = 0.2
EPSILON = 0.9
GAMMA = 1

DEFAULT_VAL = 0
MENHIR_NEIGHBOURHOOD_DISTANCE = 5

EXPLORATION_RATE = 1
MAX_EXPLORATION_RATE = 1
MIN_EXPLORATION_RATE = 0.01
EXPLORATION_DECAY_RATE = 0.001


class States(Enum):
    THE_SAME_QUARTER = 0
    OPPOSITE_QUARTERS = 1
    NEIGHBOR_QUARTERS = 2


class Actions(Enum):
    HIDE_IN_THE_STARTING_QUARTER = 0
    HIDE_IN_THE_OPPOSITE_QUARTER = 1
    HIDE_IN_THE_NEIGHBOR_QUARTER_HORIZONTAL = 2
    HIDE_IN_THE_NEIGHBOR_QUARTER_VERTICAL = 3


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class TupTupController:
    def __init__(self, name_suffix):
        self.identifier: str = "TupTup" + name_suffix
        self.menhir_pos: coordinates.Coords = None
        self.facing: Optional[characters.Facing] = None
        self.position: coordinates.Coords = None
        self.weapon: Type[weapons.Weapon] = weapons.Knife
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()
        self.has_calculated_path: bool = False
        self.path: List = []
        self.bfs_goal: coordinates.Coords = None
        self.bfs_potential_goals: Set[coordinates.Coords] = set()
        self.bfs_potential_goals_visited: Set[coordinates.Coords] = set()
        self.map: Optional[arenas.Terrain] = None
        self.map_size: Optional[Tuple[int, int]] = None
        self.hiding_spot: coordinates.Coords = None
        self.mist_radius: int = 0
        self.episode: int = 0
        self.max_num_of_episodes: int = 0

        self.Q: Dict = {}
        self.alpha: float = ALPHA
        self.epsilon: float = EPSILON
        self.discount_factor: float = GAMMA
        self.attempt_no: int = 0
        self.action: Optional[Actions] = None
        self.state: Optional[States] = None
        self.reward_sum: float = 0.0
        self.initial_position: coordinates.Coords = None
        self.last_episode_when_lived: int = 0
        self.reward: int = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TupTupController) and other.name == self.name:
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.identifier)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.attempt_no += 1
        if self.attempt_no > 1:
            self.reward = self.__get_reward()

        self.action_queue = SimpleQueue()
        self.path = []
        self.bfs_potential_goals = set()
        self.bfs_potential_goals_visited = set()
        self.has_calculated_path = False
        self.hiding_spot = None
        self.episode = 0
        self.last_episode_when_lived: int = 0

        arena = arenas.Arena.load(arena_description.name)
        self.map = arena.terrain
        self.map_size = arena.size
        self.mist_radius = int(self.map_size[0] * 2 ** 0.5) + 1
        self.max_num_of_episodes = (self.mist_radius - 1) * games.MIST_TTH
        self.menhir_pos = arena_description.menhir_position
        self.bfs_goal = self.menhir_pos
        self.bfs_potential_goals_visited.add(self.menhir_pos)

        if self.attempt_no > 200:
            self.epsilon = MIN_EXPLORATION_RATE + (MAX_EXPLORATION_RATE - MIN_EXPLORATION_RATE) * np.exp(
                -EXPLORATION_DECAY_RATE * self.attempt_no)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.episode += 1
        if knowledge:
            self.last_episode_when_lived += 1
        try:
            # if self.episode == 1:
                # print("\nGAME #", self.attempt_no)
            self.__update_char_info(knowledge)
            if self.episode == 1:
                self.initial_position = self.position

            if self.attempt_no == 1 and self.episode == 1:  # if that is the very first game choose the action randomly
                first_action = random.choice(list(Actions))
                self.action = first_action
                self.state = self.__discretize()
            elif self.attempt_no > 1 and self.episode == 1:  # learn when a new game begins but after the first game
                reward = self.reward
                action = self.action
                state = self.state
                new_action = self.__pick_action(state)
                new_state = self.__discretize()
                self.__learn(action, state, reward, new_action, new_state)
                # print("PREV ACTION ", action, " PRE STATE ", state, "\nNEW ACTION ", new_action, " NEW STATE ",
                #       new_state)
                self.action = new_action
                self.state = new_state
                self.reward_sum += reward

            if self.episode == 1 and self.__needs_to_hide():
                self.__go_to_hiding_spot()

            if self.__is_enemy_in_range(knowledge.position, knowledge.visible_tiles):
                return characters.Action.ATTACK

            if not self.action_queue.empty():
                return self.action_queue.get()

            if not self.has_calculated_path:
                start, end = self.position, self.bfs_goal
                self.__calculate_optimal_path(start, end)

                if len(self.path) > 0:  # the path was found
                    self.has_calculated_path = True
                else:
                    neighbors = self.__get_neighbors(self.bfs_goal)
                    for neighbor in neighbors:
                        if neighbor not in self.bfs_potential_goals_visited:
                            self.bfs_potential_goals.add(neighbor)
                    if self.bfs_potential_goals:
                        self.bfs_goal = self.bfs_potential_goals.pop()
                        self.bfs_potential_goals_visited.add(self.bfs_goal)

            if not self.action_queue.empty():
                return self.action_queue.get()

            if len(self.path) > 1 and self.__has_to_move():
                self.__add_moves(2)
            else:  # the destination is reached
                self.__guard_area()

            if not self.action_queue.empty():
                return self.action_queue.get()

            return characters.Action.DO_NOTHING
        except Exception:
            return characters.Action.DO_NOTHING

    def __update_char_info(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position
        char_description = knowledge.visible_tiles[knowledge.position].character
        weapons_map = {w.__name__.lower(): w for w in [weapons.Knife, weapons.Sword, weapons.Bow,
                                                       weapons.Amulet, weapons.Axe]}
        self.weapon = weapons_map.get(char_description.weapon.name, weapons.Knife)
        self.facing = char_description.facing

    def __needs_to_hide(self) -> bool:
        quarter = (self.position[0] // (self.map_size[0] / 2), self.position[1] // (self.map_size[1] / 2))
        start_x, start_y = 0, 0
        if self.action == Actions.HIDE_IN_THE_STARTING_QUARTER:
            start_x = self.map_size[0] - 1 if quarter[0] == 1.0 else 0
            start_y = self.map_size[1] - 1 if quarter[1] == 1.0 else 0
        elif self.action == Actions.HIDE_IN_THE_OPPOSITE_QUARTER:
            start_x = self.map_size[0] - 1 if quarter[0] == 0.0 else 0
            start_y = self.map_size[1] - 1 if quarter[1] == 0.0 else 0
        elif self.action == Actions.HIDE_IN_THE_NEIGHBOR_QUARTER_VERTICAL:
            start_x = self.map_size[0] - 1 if quarter[0] == 1.0 else 0
            start_y = self.map_size[1] - 1 if quarter[1] == 0.0 else 0
        elif self.action == Actions.HIDE_IN_THE_NEIGHBOR_QUARTER_HORIZONTAL:
            start_x = self.map_size[0] - 1 if quarter[0] == 0.0 else 0
            start_y = self.map_size[1] - 1 if quarter[1] == 1.0 else 0

        corner = {(start_x, start_y)}
        while not self.hiding_spot:
            for t in corner:
                if t in self.map and self.map[t].terrain_passable():
                    self.hiding_spot = coordinates.Coords(t[0], t[1])
                    break
            corner.update([(t[0] + d[0], t[1] + d[1]) for t in corner for d in [(0, 1), (0, -1), (1, 0), (-1, 0)]])

        # menhir_quarter = (self.menhir_pos[0] // (self.map_size[0] / 2), self.menhir_pos[1] // (self.map_size[1] / 2))
        # hiding_quarter = (self.hiding_spot[0] // (self.map_size[0] / 2), self.hiding_spot[1] // (self.map_size[1] / 2))
        # print("STATE", self.state, " starting quarter ", quarter, " menhir quarter ",
        #       menhir_quarter)
        # print("hiding direction ", self.action,
        #       " hiding spot quarter ", hiding_quarter)
        return True

    def __go_to_hiding_spot(self) -> None:
        start, end = self.position, self.hiding_spot
        self.__calculate_optimal_path(start, end)
        self.path.append(end)
        self.__add_moves(200)

    def __rotate(self, expected_facing: characters.Facing, starting_facing: characters.Facing = None) -> None:
        curr_facing_index = FACING_ORDER.index(self.facing if not starting_facing else starting_facing)
        expected_facing_index = FACING_ORDER.index(expected_facing)

        diff_expected_curr = expected_facing_index - curr_facing_index
        if diff_expected_curr < 0:
            diff_expected_curr += len(FACING_ORDER)

        if diff_expected_curr == 1:
            self.action_queue.put(characters.Action.TURN_RIGHT)
        elif diff_expected_curr == 2:
            self.action_queue.put(characters.Action.TURN_RIGHT)
            self.action_queue.put(characters.Action.TURN_RIGHT)
        elif diff_expected_curr == 3:
            self.action_queue.put(characters.Action.TURN_LEFT)

    def __has_to_move(self) -> bool:
        return self.episode >= self.max_num_of_episodes - len(self.path) * 5

    def __guard_area(self) -> None:
        self.action_queue.put(characters.Action.TURN_RIGHT)

    def __is_enemy_in_range(self, position: coordinates.Coords,
                            visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
        try:
            if issubclass(self.weapon, weapons.LineWeapon):
                weapon_reach = self.weapon.reach()
                tile_to_check = position
                for _ in range(1, self.weapon.reach() + 1):
                    tile_to_check = tile_to_check + self.facing.value
                    if visible_tiles[tile_to_check].character:
                        return True
            elif isinstance(self.weapon, weapons.Amulet):
                for tile in [position + (1, 1), position + (-1, 1), position + (1, -1), position + (-1, -1)]:
                    if tile in visible_tiles and visible_tiles[tile].character:
                        return True
            elif isinstance(self.weapon, weapons.Axe):
                tiles_to_check = [coordinates.Coords(self.facing.value.x, i) for i in [-1, 0, 1]] \
                    if self.facing.value.x != 0 else [coordinates.Coords(i, self.facing.value.y) for i in [-1, 0, 1]]
                for tile in tiles_to_check:
                    if tile in visible_tiles and visible_tiles[position + self.facing.value].character:
                        return True
            else:
                return False
        except KeyError:  # tile was not visible
            return False

    def __get_neighbors(self, coords):
        available_cells = []
        for facing in characters.Facing:
            next_coords = coords + facing.value
            if next_coords in self.map and self.map[coords].terrain_passable():
                available_cells.append(next_coords)
        return available_cells

    def __breadth_first_search(self, start_coords: coordinates.Coords, end_coords: coordinates.Coords) -> \
            Dict[coordinates.Coords, Tuple[int, coordinates.Coords]]:
        queue = SimpleQueue()
        if self.map[start_coords].terrain_passable():
            queue.put(start_coords)
        visited = set()
        path = {start_coords: start_coords}

        while not queue.empty():
            cell = queue.get()
            if cell in visited:
                continue
            if cell == end_coords:
                return path
            visited.add(cell)
            for neighbour in self.__get_neighbors(cell):
                if neighbour not in path:
                    path[neighbour] = cell
                queue.put(neighbour)
        raise BFSException("The shortest path wasn't found!")

    def __backtrack_path(self, end_coords: coordinates.Coords, start_coords: coordinates.Coords, path: Dict,
                         final_path: List):
        if end_coords == start_coords:
            return self.facing, end_coords
        elif end_coords not in path.keys():
            raise PathFindingException
        else:
            next_coord = path[end_coords]
            prev_facing, prev_coords = self.__backtrack_path(next_coord, start_coords, path, final_path)
            next_facing = characters.Facing(end_coords - next_coord)
            final_path.append(next_coord)
            return next_facing, next_coord

    def __get_rotations_number(self, current_facing: characters.Facing, next_facing: characters.Facing) -> int:
        curr_facing_index = FACING_ORDER.index(current_facing)
        next_facing_index = FACING_ORDER.index(next_facing)
        diff = next_facing_index - curr_facing_index
        if diff < 0:
            diff += len(FACING_ORDER)
        if diff % 2 != 0:
            return 1
        elif diff == 2:
            return 2
        return 0

    def __calculate_optimal_path(self, start_coords: coordinates.Coords, end_coords: coordinates.Coords):
        try:
            bfs_res = self.__breadth_first_search(start_coords, end_coords)
            final_path = []
            self.__backtrack_path(end_coords, start_coords, bfs_res, final_path)
            self.path = final_path
        except (BFSException, PathFindingException) as e:
            pass

    def __add_moves(self, number_of_moves=1) -> None:
        starting_facing = None
        for _ in range(number_of_moves):
            if len(self.path) < 2:
                break
            start_coords = self.path.pop(0)
            end_coords = self.path[0]
            starting_facing = self.__move(start_coords, end_coords, starting_facing)

    def __move(self, start_coords: coordinates.Coords, end_coords: coordinates.Coords,
               starting_facing: characters.Facing = None) -> characters.Facing:
        try:
            destination_facing = self.__get_destination_facing(end_coords, start_coords)
            self.__rotate(destination_facing, starting_facing)
            self.action_queue.put(characters.Action.STEP_FORWARD)
            return destination_facing
        except Exception:
            pass

    def __get_destination_facing(self, end_coords: coordinates.Coords,
                                 start_coords: coordinates.Coords) -> characters.Facing:
        coords_diff = end_coords - start_coords
        if coords_diff.y == 0:
            if coords_diff.x < 0:
                return characters.Facing.LEFT
            if coords_diff.x > 0:
                return characters.Facing.RIGHT
        elif coords_diff.x == 0:
            if coords_diff.y < 0:
                return characters.Facing.UP
            if coords_diff.y > 0:
                return characters.Facing.DOWN
        else:
            # one of the numbers SHOULD be 0, otherwise sth is wrong with the BFS result
            raise (Exception("The coordinates are not one step away from each other"))

    @property
    def name(self) -> str:
        return self.identifier

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.YELLOW

    def __discretize(self):
        start_quarter = (self.position[0] // (self.map_size[0] / 2), self.position[1] // (self.map_size[1] / 2))
        menhir_quarter = (self.menhir_pos[0] // (self.map_size[0] / 2), self.menhir_pos[1] // (self.map_size[1] / 2))
        if start_quarter == menhir_quarter:
            return States.THE_SAME_QUARTER
        elif (start_quarter[0] + menhir_quarter[0], start_quarter[1] + menhir_quarter[1]) == (1.0, 1.0):
            return States.OPPOSITE_QUARTERS
        else:
            return States.NEIGHBOR_QUARTERS

    def was_killed_by_mist(self) -> bool:
        mist_free_radius_when_died = self.mist_radius - self.last_episode_when_lived // games.MIST_TTH
        radius_distance_to_menhir = int(((self.position[0] - self.menhir_pos[0]) ** 2 +
                                         (self.position[1] - self.menhir_pos[1]) ** 2) ** 0.5)
        return mist_free_radius_when_died <= radius_distance_to_menhir

    def __get_reward(self) -> int:
        killed_by_mist = self.was_killed_by_mist()
        reward = 0
        if killed_by_mist:
            reward -= 1  # todo what if was killed by mist but also was the last one standing

        if not self.hiding_spot and self.initial_position == self.position:  # camping in the initial position
            reward -= 4
        elif not self.has_calculated_path:  # going to the hiding place
            reward -= 3
        elif len(self.path) > 0 and self.path[0] == self.hiding_spot:  # camping in the hiding place
            reward -= 2
        elif len(self.path) > MENHIR_NEIGHBOURHOOD_DISTANCE and self.path[0] != self.hiding_spot:  # going to the menhir position
            reward -= 1
        elif len(self.path) < MENHIR_NEIGHBOURHOOD_DISTANCE:  # camping near the menhir position
            reward += 3
        # print("Was killed by mist? ", killed_by_mist, " \treward ", reward)
        return reward

    def __pick_action(self, state: States) -> Actions:
        if np.random.uniform() < self.epsilon:
            return random.choice(list(Actions))
        else:
            index = np.argmax([self.Q.get((state, Actions.HIDE_IN_THE_STARTING_QUARTER), DEFAULT_VAL),
                               self.Q.get((state, Actions.HIDE_IN_THE_OPPOSITE_QUARTER), DEFAULT_VAL),
                               self.Q.get((state, Actions.HIDE_IN_THE_NEIGHBOR_QUARTER_HORIZONTAL), DEFAULT_VAL),
                               self.Q.get((state, Actions.HIDE_IN_THE_NEIGHBOR_QUARTER_VERTICAL), DEFAULT_VAL)])
            return Actions(index)

    def __learn(self, action: Actions, state: States, reward: int, new_action: Actions, new_state: States):
        old_value = self.Q.get((state, action), DEFAULT_VAL)
        future_value = self.Q.get((new_state, new_action), DEFAULT_VAL)
        if (state, action) not in self.Q.keys():
            self.Q[(state, action)] = 0.0
        self.Q[(state, action)] += self.alpha * (reward + self.discount_factor * future_value - old_value)
        # print("KNOWLEDGE \n", self.Q)


class BFSException(Exception):
    pass


class PathFindingException(Exception):
    pass


POTENTIAL_CONTROLLERS = [
    TupTupController('Bot'),
]
