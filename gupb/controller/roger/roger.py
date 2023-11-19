import random

from typing import Optional, List
import traceback

from pathfinding.core.grid import Grid
from pathfinding.core.node import GridNode
from pathfinding.finder.a_star import AStarFinder

from gupb import controller
from gupb.controller.roger.map_manager import MapManager
from gupb.controller.roger.weapon_manager import WeaponManager
from gupb.controller.roger.constans_and_types import WeaponValue, States, EpochNr
from gupb.controller.roger.utils import get_distance
from gupb.model import arenas, coordinates
from gupb.model import characters
from gupb.model.coordinates import Coords
from gupb.model.tiles import Land, Menhir


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Roger(controller.Controller):
    def __init__(self, _id: str):
        self._id = _id
        self.current_position: Optional[coordinates.Coords] = None
        # remembering map
        self.epoch: EpochNr = 0
        # pathfinding
        self.grid: Optional[Grid] = None
        self.finder = AStarFinder()
        self.actions_iterator = 0
        self.actions = []
        self.current_state = States.RANDOM_WALK
        self.beginning_iterator = 0
        self.arena = MapManager()
        self.weapon_manager = WeaponManager()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Roger):
            return self._id == other._id
        return False

    def __hash__(self) -> int:
        return hash(self._id)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.repair_knowledge(knowledge)
        self.update_state(knowledge)
        match self.current_state:
            case States.RANDOM_WALK:
                return self.random_walk()
            case States.HEAD_TO_WEAPON:
                return self.head_to_weapon([])
            case States.HEAD_TO_MENHIR:
                return self.head_to_menhir([])
            case States.FINAL_DEFENCE:
                return self.final_defence()
            case States.HEAD_TO_CENTER:
                return self.head_to_center([])
            case States.HEAD_TO_POTION:
                return self.head_to_potion([])

    def repair_knowledge(self, knowledge: characters.ChampionKnowledge):
        new_visible_tiles = {}
        for coords, item in knowledge.visible_tiles.items():
            if isinstance(coords, Coords):
                new_visible_tiles[coords] = item
            if isinstance(coords, tuple):
                new_coords = Coords(*coords)
                new_visible_tiles[new_coords] = item
        knowledge.visible_tiles.clear()
        for key, val in new_visible_tiles.items():
            knowledge.visible_tiles[key] = val

    def get_path(self, dest: Coords) -> List[GridNode]:
        self.build_grid()
        x, y = self.current_position
        x_dest, y_dest = dest
        finder = AStarFinder()
        path, _ = finder.find_path(self.grid.node(x, y), self.grid.node(x_dest, y_dest), self.grid)
        return path

    def random_walk(self, omit_finish_search=False) -> characters.Action:
        coords = self.arena.find_nearest_mist_coords()
        if coords and not omit_finish_search:
            distance_squared = (coords.x - self.current_position.x) ** 2 + (coords.y - self.current_position.y) ** 2
            if distance_squared < 64:
                return self.head_to_finish()
        if self.arena.potions_coords:
            path = self.get_path(self.arena.get_nearest_potion_coords())
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_POTION
                return self.head_to_potion(path)
        if self.arena.weapons_coords and not omit_finish_search:
            best_weapon_coords = self.get_current_best_weapon_coords()
            if best_weapon_coords:
                path = self.get_path(best_weapon_coords)
                if path:
                    self.actions = None
                    self.actions_iterator = 0
                    self.current_state = States.HEAD_TO_WEAPON
                    return self.head_to_weapon(path)

        return self.explore_map()

    def get_current_best_weapon_coords(self) -> Optional[Coords]:
        if self.current_weapon().name == "bow_unloaded" or self.current_weapon().name == "bow_loaded":
            return None
        sorted_weapon_coords = sorted(self.arena.weapons_coords.keys(), key=lambda coords: get_distance(Coords(coords[0], coords[1]), self.current_position))
        nearest_weapon_coords = sorted_weapon_coords[0]
        if WeaponValue[self.current_weapon().name.upper()].value < WeaponValue[self.arena.weapons_coords[nearest_weapon_coords].name.upper()].value:
            if nearest_weapon_coords != self.current_position:
                return nearest_weapon_coords
            else:
                return None
        return None

    def chose_next_tile(self) -> Coords:
        walkable = list(filter(lambda x: isinstance(x[1], Land) or isinstance(x[1], Menhir), self.arena.terrain.items()))
        walkable_coords = set(map(lambda x: x[0], walkable))
        seen_coords = set(self.arena.seen_tiles.keys())
        unseen_coords = walkable_coords - seen_coords
        unseen_coords = list(unseen_coords)
        best_coords = random.choices(list(walkable_coords), k=1)[0]
        if unseen_coords:
            k = min(10, len(unseen_coords))
            random_unseen = random.choices(unseen_coords, k=k)
        else:
            return best_coords
        longest_path_len = 0
        for coords in random_unseen:
            path = self.get_path(coords)
            if path:
                path_len = len(self.map_path_to_action_list(self.current_position, path))
                if path_len > longest_path_len:
                    longest_path_len = path_len
                    best_coords = coords
        return best_coords

    def chose_next_tile_neighbourhood(self) -> Coords:
        walkable = list(filter(lambda x: isinstance(x[1], Land) or isinstance(x[1], Menhir), self.arena.terrain.items()))
        walkable_coords = list(map(lambda x: x[0], walkable))
        nearest_walkable_coords = set(filter(lambda x: get_distance(self.current_position, x) < 5, walkable_coords))
        seen_coords = set(self.arena.seen_tiles.keys())
        unseen_coords = nearest_walkable_coords - seen_coords
        unseen_coords = list(unseen_coords)
        best_coords = random.choices(list(walkable_coords), k=1)[0]
        if unseen_coords:
            k = min(10, len(unseen_coords))
            random_unseen = random.choices(unseen_coords, k=k)
        else:
            return best_coords
        longest_path_len = 0
        for coords in random_unseen:
            path = self.get_path(coords)
            if path:
                path_len = len(self.map_path_to_action_list(self.current_position, path))
                if path_len > longest_path_len:
                    longest_path_len = path_len
                    best_coords = coords
        return best_coords

    def explore_map(self):
        if self.actions and self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0

        if not self.actions:
            new_aim = self.chose_next_tile_neighbourhood()
            path = self.get_path(new_aim)
            actions = self.map_path_to_action_list(self.current_position, path)
            self.actions = actions
            self.actions_iterator = 0
        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def return_attack_if_enemy_in_cut_range(self, action: characters.Action):
        if not action == characters.Action.ATTACK:
            cut_positions = self.weapon_manager.get_weapon_cut_positions(self.arena, self.current_position, self.current_weapon().name)
            for cut_position in cut_positions:
                if self.arena.seen_tiles.get(cut_position):
                    if self.arena.seen_tiles[cut_position][1] == self.epoch and self.arena.seen_tiles[cut_position][0].character:
                        self.actions_iterator -= 1
                        return characters.Action.ATTACK
        return action



    # def return_attack_if_enemy_on_the_road(self, action: characters.Action):
    #     if action == characters.Action.STEP_FORWARD:
    #         action = self.return_attack_if_enemy_ahead(action)
    #     return action

    def head_to_finish(self) -> characters.Action:
        if self.arena.menhir_coords:
            path = self.get_path(self.arena.menhir_coords)
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_MENHIR
                return self.head_to_menhir(path)
        else:
            path = self.get_path(Coords(self.arena.arena_size[0]//2, self.arena.arena_size[1]//2))
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_CENTER
                return self.head_to_center(path)

        self.current_state = States.RANDOM_WALK
        return self.random_walk(omit_finish_search=True)

    def head_to_weapon(self, path: List[GridNode]) -> characters.Action:
        coords = self.arena.find_nearest_mist_coords()
        if coords:
            distance_squared = (coords.x - self.current_position.x) ** 2 + (coords.y - self.current_position.y) ** 2
            if distance_squared < 64:
                self.actions = None
                self.actions_iterator = 0
                return self.head_to_finish()
        if self.arena.potions_coords:
            path = self.get_path(self.arena.get_nearest_potion_coords())
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_POTION
                return self.head_to_potion(path)
        if not self.actions:
            self.actions = self.map_path_to_action_list(self.current_position, path)
        if self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0
            self.current_state = States.RANDOM_WALK
            return self.random_walk()

        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def head_to_menhir(self, path: List[GridNode]) -> characters.Action:
        if not self.actions:
            self.actions = self.map_path_to_action_list(self.current_position, path)
        if self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0
            self.current_state = States.FINAL_DEFENCE
            return self.final_defence()

        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def final_defence(self) -> characters.Action:
        self.actions = [characters.Action.TURN_RIGHT, characters.Action.ATTACK]
        action = self.actions[self.actions_iterator % 2]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def head_to_center(self, path) -> characters.Action:
        if not self.actions:
            self.actions = self.map_path_to_action_list(self.current_position, path)
        if self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0
            self.current_state = States.FINAL_DEFENCE
            return self.final_defence()

        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        return action

    def head_to_potion(self, path: List[GridNode]) -> characters.Action:
        if not self.actions:
            self.actions = self.map_path_to_action_list(self.current_position, path)
        if self.actions_iterator >= len(self.actions):
            self.actions = None
            self.actions_iterator = 0
            # self.arena.potions_coords = None todo check if ok
            self.current_state = States.RANDOM_WALK
            return self.random_walk()

        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def update_state(self, knowledge: characters.ChampionKnowledge):
        self.epoch += 1
        self.current_position = Coords(*knowledge.position)
        self.arena.update(self.current_position, self.epoch, knowledge.visible_tiles)

    def map_path_to_action_list(self, current_position: Coords, path: List[GridNode]) -> List[characters.Action]:
        initial_facing = self.arena.seen_tiles[current_position][0].character.facing
        facings: List[characters.Facing] = list(
            map(lambda a: characters.Facing(Coords(a[1].x - a[0].x, a[1].y - a[0].y)), list(zip(path[:-1], path[1:]))))
        actions: List[characters.Action] = []
        for a, b in zip([initial_facing, *facings[:-1]], facings):
            actions.extend(self.map_facings_to_actions(a, b))
        return actions

    def map_facings_to_actions(self, f1: characters.Facing, f2: characters.Facing) -> List[characters.Action]:
        if f1 == f2:
            return [characters.Action.STEP_FORWARD]
        elif f1.turn_left() == f2:
            return [characters.Action.TURN_LEFT, characters.Action.STEP_FORWARD]
        elif f1.turn_right() == f2:
            return [characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]
        else:
            return [characters.Action.TURN_RIGHT, characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        # reset round unique variables
        self.epoch = 0
        self.actions = None
        self.actions_iterator = 0
        self.current_state = States.RANDOM_WALK
        self.arena.reset(arena_description.name)


    def extract_walkable_tiles(self, items=None):
        if items is None:
            items = self.arena.terrain.items()
        try:
            return list(filter(lambda x: isinstance(x[1], Land) or isinstance(x[1], Menhir), items))
        except AttributeError:
            return list(filter(lambda x: x[1][0].type == 'land' or x[1][0].type == 'menhir', items))

    def build_grid(self):
        walkable_tiles_list = self.extract_walkable_tiles()
        walkable_tiles_matrix = [[0 for y in range(self.arena.arena_size[1])] for x in range(self.arena.arena_size[0])]

        for tile in walkable_tiles_list:
            x, y = tile[0]
            walkable_tiles_matrix[y][x] = 1

        self.grid = Grid(self.arena.arena_size[0], self.arena.arena_size[1], walkable_tiles_matrix)

    def current_weapon(self):
        return self.arena.seen_tiles[self.current_position][0].character.weapon

    @property
    def name(self) -> str:
        return f'Roger_{self._id}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED

    def get_safe_tiles(self) -> List[Coords]:
        tiles_around = self.arena.get_4_tiles_around()
        tiles_available = self.extract_walkable_tiles(tiles_around)  #todo uogólnić
        tiles_available_set = set(tiles_available)
        unsafe_tiles = []
        for coords, seen_enemy in self.arena.enemies_coords.items():
            cut_tiles = self.weapon_manager.get_weapon_cut_positions(self.arena, coords, seen_enemy.enemy.weapon.name)
            unsafe_tiles.extend(cut_tiles)
        unsafe_tiles_set = set(unsafe_tiles)
        safe_tiles = tiles_available_set.difference(unsafe_tiles_set)
        safe_tiles = list(safe_tiles)
        return safe_tiles




