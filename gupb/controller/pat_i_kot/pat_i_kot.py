import random
import numpy as np
from math import sqrt

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action
from gupb.model.coordinates import Coords

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]


def distance(coords, other_coords):
    return sqrt((coords[0] - other_coords[0]) ** 2 + (coords[1] - other_coords[1]) ** 2)


class PatIKotController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.facing = None
        self.menhir_location = None
        self.target = Coords(25, 25)
        self.mist_spotted = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PatIKotController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles

        available_actions = POSSIBLE_ACTIONS.copy()

        me = knowledge.visible_tiles[position].character
        self.facing = me.facing

        if self.menhir_location is None:
            for tile_coord in visible_tiles:
                if visible_tiles[tile_coord].type == 'menhir':
                    self.menhir_location = Coords(tile_coord[0], tile_coord[1])
                    self.target = self.menhir_location

        ## for random areas
        # if not self.mist_spotted:
        #     for tile_coord in visible_tiles:
        #         if "mist" in list(map(lambda x: x.type, visible_tiles[tile_coord].effects)):
        #             self.target = self.menhir_location
        #             self.mist_spotted = True

        next_block = position + self.facing.value
        if next_block in visible_tiles:
            if visible_tiles[next_block].type in ['sea', 'wall']:
                available_actions = [x for x in available_actions if x not in [Action.STEP_FORWARD, Action.ATTACK]]
            if visible_tiles[next_block].character is None:
                available_actions = [x for x in available_actions if x not in [Action.ATTACK]]
            if visible_tiles[next_block].character is not None:
                available_actions = [Action.ATTACK]

        if Action.STEP_FORWARD in available_actions:
            distance_from_target = distance(self.target, position)
            if distance_from_target > 100:
                if np.random.rand() < 0.8:
                    return Action.STEP_FORWARD
            else:
                if np.random.rand() < 0.5:
                    return Action.STEP_FORWARD

        if Action.ATTACK not in available_actions:
            left_ahead = distance(self.target, position + self.facing.turn_left().value)
            right_ahead = distance(self.target, position + self.facing.turn_right().value)

            if left_ahead < right_ahead:
                return Action.TURN_LEFT if np.random.rand() < 0.7 else Action.TURN_RIGHT
            else:
                return Action.TURN_RIGHT if np.random.rand() < 0.7 else Action.TURN_LEFT

        return random.choice(available_actions)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.facing = None
        self.menhir_location = None
        self.target = Coords(25, 25)

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PIKACHU