from typing import List
import numpy as np
from enum import Enum
from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action, Facing
from gupb.model.coordinates import Coords, add_coords, sub_coords

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
        find_path(arr=self.__map_ref,
                  visited=np.zeros_like(self.__map_ref),
                  curr_pos=position,
                  path=found_path)
        actions = []
        curr_direction = direction
        for i in range(len(found_path)-1):
            direction = sub_coords(found_path[i], found_path[i-1])

            curr_direction = direction


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
        pass

    def get_facing(self, knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[knowledge.position].character.facing

    def get_facing_element(self, knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[add_coords(knowledge.position, self.get_facing(knowledge).value)]

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

        self.path_finder.find_path(knowledge.position)


    def wander(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # The wandering algorithm is running in circles until we find a wall or enemy
        x = knowledge.position.x
        y = knowledge.position.y
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            try:
                step_forward = Coords(x=x + dx, y=y + dy)
                if knowledge.visible_tiles[step_forward].type == "land":
                    if knowledge.visible_tiles[step_forward].character is not None:
                        return Action.ATTACK
                    else:
                        self.update_map(knowledge)
                        return Action.STEP_FORWARD
            except KeyError:
                pass

        self.update_map(knowledge)
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

