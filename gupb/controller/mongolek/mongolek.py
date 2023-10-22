import random
import numpy as np

from gupb import controller
from gupb.controller.mongolek.astar import astar
from gupb.model import arenas, effects
from gupb.model import characters
from gupb.model.characters import Action, Facing
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]
POSSIBLE_MOVES = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
]

weapon_list = ['knife',
               'amulet',
               'sword',
               'bow',
               'axe']


class Mongolek(controller.Controller):
    def __init__(self, first_name: str):
        self.menhir_position = None
        self.first_name: str = first_name
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = False
        self.mist_positions = []
        self.target = None
        self.enemy = None
        self.move_list = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mongolek):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.move_number += 1
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles

        me = knowledge.visible_tiles[position].character
        self.facing = me.facing
        self.health = me.health
        self.weapon = me.weapon

        if not self.menhir_found:
            for tile in visible_tiles:
                if visible_tiles[tile] == 'menhir':
                    self.menhir_found = True
                    self.target = Coords(tile[0], tile[1])
                    self.menhir_position = Coords(tile[0], tile[1])
                    # self.move_list = astar(visible_tiles, position, self.target)
                    break
                if visible_tiles[tile] == 'mist':
                    self.mist_positions.append(Coords(tile[0], tile[1]))
                elif not self.weapon and visible_tiles[tile] in weapon_list:
                    self.target = Coords(tile[0], tile[1])
                    # self.move_list = astar(visible_tiles, position, self.target)
                elif visible_tiles[tile].character:
                    self.enemy = Coords(tile[0], tile[1])

        if self.enemy[0] == self.facing.value[0] + position[0] and self.enemy[1] == self.facing.value[1] + position[1]:
            return Action.ATTACK
        elif self.target and self.move_list:
            idx = self.move_list.pop(0)
            if idx == 0:
                return Action.TURN_LEFT
            elif idx == 1:
                return Action.TURN_RIGHT
            else:
                return Action.STEP_FORWARD
        else:
            self.target = None
            next_tile = position + self.facing.value
            if visible_tiles[next_tile].type in ['sea', 'wall']:
                return Action.TURN_RIGHT
            possible = [1, 1, 4]
            return random.choices(POSSIBLE_MOVES, possible, k=1)[0]

    def praise(self, score: int) -> None:
        raise NotImplementedError

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = False
        self.target = None

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.MONGOL


POTENTIAL_CONTROLLERS = [
    Mongolek("Mongolek"),
]
