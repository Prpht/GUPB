import random
import traceback

from typing import Optional, List

from pathfinding.core.node import GridNode
from pathfinding.finder.a_star import AStarFinder

from gupb import controller
from gupb.controller.roger.map_manager import MapManager
from gupb.controller.roger.weapon_manager import get_weapon_cut_positions
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
        self.finder = AStarFinder()
        self.actions_iterator = 0
        self.actions = []
        self.current_state = States.RANDOM_WALK
        self.beginning_iterator = 0
        self.arena = MapManager()

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

    def random_walk(self, omit_finish_search=False) -> characters.Action:
        coords = self.arena.find_nearest_mist_coords()
        if coords and not omit_finish_search:
            distance_squared = (coords.x - self.current_position.x) ** 2 + (coords.y - self.current_position.y) ** 2
            if distance_squared < 64:
                return self.head_to_finish()
        if self.arena.in_cut_range:
            safe_tiles = self.arena.get_safe_tiles()
            if safe_tiles:
                path = self.arena.get_path(safe_tiles[0])
                if path:
                    actions = self.arena.map_path_to_action_list(self.current_position, path, True)
                    self.actions = actions
                    self.actions_iterator = 0
                    return self.explore_map()
        if self.arena.potions_coords:
            path = self.arena.get_path(self.arena.get_nearest_potion_coords())
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_POTION
                return self.head_to_potion(path)
        if self.arena.weapons_coords and not omit_finish_search:
            best_weapon_coords = self.get_current_best_weapon_coords()
            if best_weapon_coords:
                path = self.arena.get_path(best_weapon_coords)
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
            path = self.arena.get_path(coords)
            if path:
                path_len = len(self.arena.map_path_to_action_list(self.current_position, path))
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
            path = self.arena.get_path(coords)
            if path:
                path_len = len(self.arena.map_path_to_action_list(self.current_position, path))
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
            path = self.arena.get_path(new_aim)
            actions = self.arena.map_path_to_action_list(self.current_position, path)
            self.actions = actions
            self.actions_iterator = 0
        action = self.actions[self.actions_iterator]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def return_attack_if_enemy_in_cut_range(self, action: characters.Action):
        if not action == characters.Action.ATTACK:
            cut_positions = get_weapon_cut_positions(self.arena.seen_tiles, self.arena.terrain, self.current_position, self.current_weapon().name)
            for cut_position in cut_positions:
                if self.arena.seen_tiles.get(cut_position):
                    potential_enemy = self.arena.seen_tiles[cut_position][0].character
                    if self.arena.seen_tiles[cut_position][1] == self.epoch and potential_enemy:
                        if not self.arena.in_cut_range:
                            self.actions_iterator -= 1
                            return characters.Action.ATTACK
                        else:
                            if self.arena.subtract_enemy_live(potential_enemy) < 0:
                                safe_tiles = self.arena.get_safe_tiles()
                                if safe_tiles:
                                    path = self.arena.get_path(safe_tiles[0])
                                    if path:
                                        actions = self.arena.map_path_to_action_list(self.current_position, path, True)
                                        if len(actions) == 1:
                                            self.actions = None
                                            self.actions_iterator = 0
                                        else:
                                            self.actions = actions
                                            self.actions_iterator = 1
                                        return actions[0]

                        self.actions_iterator -= 1
                        return characters.Action.ATTACK

        return action

    def set_potential_duel_decision(self):
        if len(self.arena.potential_attackers.items()) > 1:
            pass
        else:
            pass


    # def return_attack_if_enemy_on_the_road(self, action: characters.Action):
    #     if action == characters.Action.STEP_FORWARD:
    #         action = self.return_attack_if_enemy_ahead(action)
    #     return action

    def head_to_finish(self) -> characters.Action:
        if self.arena.menhir_coords:
            path = self.arena.get_path(self.arena.menhir_coords)
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_MENHIR
                return self.head_to_menhir(path)
        else:
            path = self.arena.get_path(Coords(self.arena.arena_size[0]//2, self.arena.arena_size[1]//2))
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
        if self.arena.in_cut_range:
            safe_tiles = self.arena.get_safe_tiles()
            if safe_tiles:
                path = self.arena.get_path(safe_tiles[0])
                if path:
                    actions = self.arena.map_path_to_action_list(self.current_position, path, True)
                    self.actions = actions
                    self.actions_iterator = 0
                    self.current_state=States.RANDOM_WALK
                    return self.explore_map()
        if self.arena.potions_coords:
            path = self.arena.get_path(self.arena.get_nearest_potion_coords())
            if path:
                self.actions = None
                self.actions_iterator = 0
                self.current_state = States.HEAD_TO_POTION
                return self.head_to_potion(path)
        if not self.actions:
            self.actions = self.arena.map_path_to_action_list(self.current_position, path)
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
            self.actions = self.arena.map_path_to_action_list(self.current_position, path, True)
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
        self.actions = [characters.Action.TURN_RIGHT, characters.Action.TURN_RIGHT, characters.Action.TURN_LEFT]
        action = self.actions[self.actions_iterator % 2]
        self.actions_iterator += 1
        action = self.return_attack_if_enemy_in_cut_range(action)
        return action

    def head_to_center(self, path) -> characters.Action:
        if not self.actions:
            self.actions = self.arena.map_path_to_action_list(self.current_position, path, True)
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
            self.actions = self.arena.map_path_to_action_list(self.current_position, path, True)
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

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        # reset round unique variables
        self.epoch = 0
        self.actions = None
        self.actions_iterator = 0
        self.current_state = States.RANDOM_WALK
        self.arena.reset(arena_description.name)

    def extract_walkable_tiles(self):
        return self.arena.extract_walkable_tiles()

    def extract_walkable_coords(self, coords: List[Coords]) -> List[Coords]:
        return self.arena.extract_walkable_coords(coords)


    def current_weapon(self):
        return self.arena.seen_tiles[self.current_position][0].character.weapon

    @property
    def name(self) -> str:
        return f'Roger_{self._id}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED





