from typing import List
from math import acos
import numpy as np
from enum import Enum
from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action, Facing
from gupb.model.coordinates import Coords, add_coords
import logging

from .utils import PathConstants, find_path
verbose_logger = logging.getLogger("verbose")


class KillerInterest(Enum):
    POINT_ON_MAP = 2
    ITEM = 3
    KILLING = 4
    MENHIR = 5


class KillerAction(Enum):
    DISCOVER = 0  # Find new point of interest on map
    FIND_PATH = 1  # Find actions to get to the destination
    FIND_VICTIM = 2  # Find path to enemy
    FIND_MENHIR = 3  # Find path to menhir if one exists
    LEARN_MAP = 4  # Invoke learn_map method
    LOOK_AROUND = 5  # Perform ('turn right', 'learn_map') 4 times
    SPIN_AROUND = 6  # Perform 'turn right' 4 times


class KillerController(controller.Controller):

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.game_map = None
        self.menhir_pos = None
        self.planned_actions = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KillerController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def learn_map(self, knowledge: characters.ChampionKnowledge) -> None:

        for coord, tile in knowledge.visible_tiles.items():

            if tile.type == "land":
                self.game_map[coord[0], coord[1]] = PathConstants.WALKABLE.value
                if tile.character is not None:
                    self.game_map[coord[0], coord[1]] = KillerInterest.KILLING.value

            if self.menhir_pos is None:
                if tile.type == "menhir":
                    self.game_map[coord[0], coord[1]] = KillerInterest.MENHIR.value
                    self.menhir_pos = coord[0], coord[1]

    def update_map(self,
                   knowledge: characters.ChampionKnowledge,
                   current_interest: KillerInterest) -> None:
        # to do: Update only player locations (not the whole map)
        pass

    def __get_path_actions(self,
                           position: Coords,
                           direction: Coords,
                           interest: KillerInterest) -> List[Action]:
        found_path = []
        is_found = find_path(arr=self.game_map,
                             visited=np.zeros_like(self.game_map),
                             curr_pos=position,
                             path=found_path,
                             min_sought_val=interest.value)
        verbose_logger.debug(f"Is path found: {is_found}")
        actions = []
        if not is_found:
            # verbose_logger.debug(f"Map: {self.game_map}")
            return actions
        # verbose_logger.debug(f"Found_path: {found_path}")

        curr_d = direction
        for i in range(len(found_path) - 1):
            d = found_path[i + 1][0] - found_path[i][0], found_path[i + 1][1] - found_path[i][1]
            sign = curr_d[0] * d[1] - d[0] * curr_d[1]
            angle = acos(d[0] * curr_d[0] + d[1] * curr_d[1])
            if 1. <= angle <= 2.5:
                if sign < 0:
                    actions.append(Action.TURN_RIGHT)
                else:
                    actions.append(Action.TURN_LEFT)
            if 2.5 <= angle:
                actions.append(Action.TURN_RIGHT)
                actions.append(Action.TURN_RIGHT)
            actions.append(Action.STEP_FORWARD)
            curr_d = d
        # verbose_logger.debug(actions)
        return actions

    def find_new_interest(self, curr_position):
        x_max, y_max = self.game_map.shape
        map = self.game_map.copy()
        map[curr_position] = 0
        stack = [curr_position]
        distances = []
        get_distance = lambda z: np.sqrt(z[0]**2 + z[1]**2)
        while stack:
            coords = stack.pop()
            if coords[0] - 1 >= 0 and map[coords[0] - 1, coords[1]] == 1:
                new_coords = coords[0] - 1, coords[1]
                map[new_coords] = 0
                distances.append((new_coords, get_distance(new_coords)))
                stack.append(new_coords)
            if coords[0] + 1 < x_max and map[coords[0] + 1, coords[1]] == 1:
                new_coords = coords[0] + 1, coords[1]
                map[new_coords] = 0
                distances.append((new_coords, get_distance(new_coords)))
                stack.append(new_coords)
            if coords[1] - 1 >= 0 and map[coords[0], coords[1] - 1] == 1:
                new_coords = coords[0], coords[1] - 1
                map[new_coords] = 0
                distances.append((new_coords, get_distance(new_coords)))
                stack.append(new_coords)
            if coords[1] + 1 < y_max and map[coords[0], coords[1] + 1] == 1:
                new_coords = coords[0], coords[1] + 1
                map[new_coords] = 0
                distances.append((new_coords, get_distance(new_coords)))
                stack.append(new_coords)
        if distances:
            self.game_map[sorted(distances, key=lambda x: x[1])[-1][0]] = 2



    @staticmethod
    def get_facing(knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[knowledge.position].character.facing

    @staticmethod
    def get_facing_element(knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[add_coords(knowledge.position, KillerController.get_facing(knowledge).value)]

    def find(self, knowledge: characters.ChampionKnowledge, interest: KillerInterest):
        # verbose_logger.debug("Looking for path...")
        current_position = knowledge.position
        # verbose_logger.debug(f"Curr position: {current_position}")
        facing = self.get_facing(knowledge)
        # verbose_logger.debug(f"Facing: {facing}")
        if facing == Facing.UP:
            curr_direction = -1, 0
        elif facing == Facing.DOWN:
            curr_direction = 1, 0
        elif facing == Facing.LEFT:
            curr_direction = 0, -1
        else:  # facing == Facing.RIGHT
            curr_direction = 0, 1
        # verbose_logger.debug(f"Current direction: {curr_direction}")
        path_actions = self.__get_path_actions(current_position, curr_direction, interest)
        # logging.debug(f"Actions to get there: {path_actions}")
        if len(path_actions) != 0:
            self.planned_actions += path_actions
            self.planned_actions.append(KillerAction.LOOK_AROUND)

    def execute_action(self, action: KillerAction, knowledge: characters.ChampionKnowledge):
        if action == KillerAction.LEARN_MAP:
            self.learn_map(knowledge)

        if action == KillerAction.LOOK_AROUND:
            self.planned_actions += 4 * [Action.TURN_RIGHT, KillerAction.LEARN_MAP]

        if action == KillerAction.SPIN_AROUND:
            self.planned_actions += 4 * [Action.TURN_RIGHT]

        if action == KillerAction.FIND_VICTIM:
            self.find(knowledge, interest=KillerInterest.KILLING)

        if action == KillerAction.FIND_MENHIR:
            self.find(knowledge, interest=KillerInterest.MENHIR)

        if action == KillerAction.DISCOVER:
            self.find_new_interest(curr_position=knowledge.position)
            self.find(knowledge, interest=KillerInterest.POINT_ON_MAP)

    def check_for_enemies(self, knowledge: characters.ChampionKnowledge):
        #mark enemies
        are_enemies = False
        for coords, value in knowledge.visible_tiles.items():
            if value.character is not None and value.character.controller_name != 'Killer':
                self.game_map[coords] = KillerInterest.KILLING.value
                are_enemies = True
        return are_enemies

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        facing_element = self.get_facing_element(knowledge)
        if facing_element.character is not None:
            return Action.ATTACK

        if self.game_map is None:
            self.game_map = np.zeros(shape=(50, 50))
            self.execute_action(KillerAction.LOOK_AROUND, knowledge)

        if self.menhir_pos == knowledge.position:
            self.execute_action(KillerAction.SPIN_AROUND, knowledge)

        # verbose_logger.debug(f"Planned actions: {self.planned_actions}")
        if len(self.planned_actions) == 0 and (self.menhir_pos is not None):
            self.execute_action(KillerAction.FIND_MENHIR, knowledge)

        if len(self.planned_actions) == 0 and self.check_for_enemies(knowledge):  # Could not find menhir
            self.execute_action(KillerAction.FIND_VICTIM, knowledge)

        if len(self.planned_actions) == 0:  # Could not find victim
            self.execute_action(KillerAction.DISCOVER, knowledge)

        # verbose_logger.debug(self.planned_actions)
        while len(self.planned_actions) > 0:
            action = self.planned_actions.pop(0)
            if isinstance(action, KillerAction):
                self.execute_action(action, knowledge)
            else:
                if action == Action.STEP_FORWARD and facing_element.type != 'land':
                    return Action.TURN_RIGHT
                else:
                    return action
        else:
            return Action.TURN_RIGHT

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED

