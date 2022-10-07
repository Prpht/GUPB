import random
import numpy as np

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


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Spejson(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = False
        self.target = Coords(25, 25)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Spejson):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.move_number += 1
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles

        available_actions = POSSIBLE_ACTIONS.copy()

        me = knowledge.visible_tiles[position].character
        self.facing = me.facing
        self.health = me.health
        self.weapon = me.weapon

        if not self.menhir_found:
            for tile_coord in visible_tiles:
                if visible_tiles[tile_coord].type == 'menhir':
                    self.target = Coords(tile_coord[0], tile_coord[1])
                    self.menhir_found = True

        # Rule out stupid moves
        next_block = position + self.facing.value
        if next_block in visible_tiles:
            if visible_tiles[next_block].type in ['sea', 'wall']:
                available_actions = [x for x in available_actions if x not in [Action.STEP_FORWARD, Action.ATTACK]]
            if visible_tiles[next_block].character is None:
                available_actions = [x for x in available_actions if x not in [Action.ATTACK]]
            if visible_tiles[next_block].character is not None:
                available_actions = [Action.ATTACK]

        if Action.STEP_FORWARD in available_actions:
            distance_from_target = self.target - position
            distance_from_target = distance_from_target.x ** 2 + distance_from_target.y ** 2
            if distance_from_target > 100:
                if np.random.rand() < 0.8:
                    return Action.STEP_FORWARD
            else:
                if np.random.rand() < 0.5:
                    return Action.STEP_FORWARD

        if Action.ATTACK not in available_actions:
            left_ahead = self.target - (position + self.facing.turn_left().value)
            left_ahead = left_ahead.x ** 2 + left_ahead.y ** 2
            right_ahead = self.target - (position + self.facing.turn_right().value)
            right_ahead = right_ahead.x ** 2 + right_ahead.y ** 2

            if left_ahead < right_ahead:
                return Action.TURN_LEFT if np.random.rand() < 0.7 else Action.TURN_RIGHT
            else:
                return Action.TURN_RIGHT if np.random.rand() < 0.7 else Action.TURN_LEFT

        return random.choice(available_actions)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = False
        self.target = Coords(25, 25)

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    Spejson("Spejson"),
]
