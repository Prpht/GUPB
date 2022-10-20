from typing import List
from math import acos
import numpy as np
from enum import Enum
from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action
from gupb.model.coordinates import Coords, add_coords

from .utils import PathConstants, find_path


class KillerInterests(Enum):
    KILLING = "killing"
    MENHIR = "menhir"
    DISCOVER = "discover"
    ITEM = "item"


class PathFinder:
    def __init__(self, map_reference):
        self.__map_ref = map_reference

    def find_path(self, position: Coords, direction: Coords) -> List[Action]:
        found_path = []
        is_found = find_path(arr=self.__map_ref,
                             visited=np.zeros_like(self.__map_ref),
                             curr_pos=position,
                             path=found_path)
        actions = []
        if not is_found:
            return actions

        curr_d = direction
        for i in range(len(found_path) - 1):
            d = found_path[i + 1][0] - found_path[i][0], found_path[i + 1][1] - found_path[i][1]
            sign = d[1] * curr_d[0] - d[0] * curr_d[1]
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
        return actions


class KillerController(controller.Controller):

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.game_map = None
        self.menhir_pos = None
        self.path_finder = None
        self.planned_actions = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KillerController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def learn_map(self,
                  knowledge: characters.ChampionKnowledge,
                  current_interest: KillerInterests) -> None:

        for coord, tile in knowledge.visible_tiles.items():

            if tile.type == "land":
                self.game_map[coord[0], coord[1]] = PathConstants.WALKABLE
                if (current_interest == KillerInterests.KILLING) and \
                   (tile.character is not None):
                    self.game_map[coord[0], coord[1]] = PathConstants.DESTINATION

            if (tile.type == "menhir") and \
               (self.menhir_pos is None):
                self.menhir_pos = coord[0], coord[1]
                if current_interest == KillerInterests.MENHIR:
                    self.game_map[coord[0], coord[1]] = PathConstants.DESTINATION

    def update_map(self,
                   knowledge: characters.ChampionKnowledge,
                   current_interest: KillerInterests) -> None:
        # TODO: Update only player locations
        pass

    @staticmethod
    def get_facing(knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[knowledge.position].character.facing

    @staticmethod
    def get_facing_element(knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[add_coords(knowledge.position, KillerController.get_facing(knowledge).value)]

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.game_map is None:
            self.game_map = np.zeros(shape=(50, 50))
            self.learn_map(knowledge, KillerInterests.MENHIR)
            self.path_finder = PathFinder(self.game_map)

        facing_element = self.get_facing_element(knowledge)
        if facing_element.character is not None:
            return Action.ATTACK

        if len(self.planned_actions) > 0:
            return self.planned_actions.pop(0)
        else:
            self.planned_actions.append(self.path_finder.find_path(knowledge.position))

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

