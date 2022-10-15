import random
import re


from gupb.model.characters import Action
import numpy as np

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates as coo

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]
DIRS_COORDS = {
    "UP": (0, 1),
    "RIGHT": (1, 0),
    "DOWN": (0, -1),
    "LEFT": (-1, 0),
}
COORDS_DIRS = {
    coo.Coords(0, 1): "UP",
    coo.Coords(1, 0): "RIGHT",
    coo.Coords(0, -1): "DOWN",
    coo.Coords(-1, 0): "LEFT",
}


class AksolotlController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.position = None
        self.knowledge = None
        self.facing = None
        self.neighbors = []
        self.neighbors_types = dict()
        self.possible_tiles = []
        self.weapon_position = None
        self.menhir_position = None
        self.action_queue = []
        self.mist_positions = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AksolotlController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def update_map(self):
        pass

    def detect_opponent(self):
        for n in self.neighbors:
            if coo.Coords(n[0], n[1]) in list(self.knowledge.visible_tiles.keys()):
                if self.knowledge.visible_tiles[coo.Coords(n[0], n[1])].character:
                    return coo.Coords(n[0], n[1])
        return None

    def check_around_for(self, type):
        for n in self.neighbors:
            if coo.Coords(n[0], n[1]) in list(self.knowledge.visible_tiles.keys()):
                info_about = self.knowledge.visible_tiles[coo.Coords(n[0], n[1])]
                if info_about.type == type:
                    return coo.Coords(n[0], n[1])
        return None

    """def unblock(self):
        self.neighbors_types = dict.fromkeys(self.neighbors)
        possible_exits = []
        for n in self.neighbors:
            if coo.Coords(n[0], n[1]) in list(self.knowledge.visible_tiles.keys()):
                self.neighbors_types[n] = self.knowledge.visible_tiles[
                    coo.Coords(n[0], n[1])
                ].type
                if self.knowledge.visible_tiles[coo.Coords(n[0], n[1])].type not in [
                    "wall",
                    "sea",
                ]:
                    possible_exits.append(coo.Coords(n[0], n[1]))
        exit_point = random.choice(possible_exits)
        self.move_to(exit_point)"""

    def update_neighbors(self):
        return [
            coo.Coords(self.position[0], self.position[1]) + coo.Coords(1, 0),
            coo.Coords(self.position[0], self.position[1]) + coo.Coords(0, 1),
            coo.Coords(self.position[0], self.position[1]) + coo.Coords(-1, 0),
            coo.Coords(self.position[0], self.position[1]) + coo.Coords(0, -1),
        ]

    def update_neighbors_types(self):
        self.neighbors_types = dict.fromkeys(self.neighbors)
        possible_tiles = self.neighbors.copy()
        for n in self.neighbors:
            if coo.Coords(n[0], n[1]) in self.knowledge.visible_tiles.keys():
                curr_type = self.knowledge.visible_tiles[coo.Coords(n[0], n[1])].type
                self.neighbors_types[n] = curr_type
                if curr_type in ["wall", "sea"]:
                    possible_tiles.remove(coo.Coords(n[0], n[1]))
        self.possible_tiles = possible_tiles

    def move_to(self, destination_coords):
        diff = coo.Coords(self.position[0], self.position[1]) - coo.Coords(
            destination_coords[0], destination_coords[1]
        )
        if abs(diff.x) > 1 or abs(diff.y) > 1:
            return
        self.rotation(COORDS_DIRS[diff])
        self.action_queue.append(Action.STEP_FORWARD)

    def move_to_opponent(self, destination_coords):
        diff = coo.Coords(self.position[0], self.position[1]) - coo.Coords(
            destination_coords[0], destination_coords[1]
        )
        if abs(diff.x) > 1 or abs(diff.y) > 1:
            return
        self.rotation(COORDS_DIRS[diff])
        self.action_queue.append(Action.ATTACK)

    def rotation(self, direction):
        if self.facing.name == direction:
            return
        diff = coo.Coords(
            DIRS_COORDS[direction][0], DIRS_COORDS[direction][1]
        ) - coo.Coords(
            DIRS_COORDS[self.facing.name][0], DIRS_COORDS[self.facing.name][1]
        )

        if abs(diff.x) == 2 or abs(diff.y) == 2:
            self.action_queue.append(Action.TURN_RIGHT)
            self.action_queue.append(Action.TURN_RIGHT)
        else:
            dirs = list(DIRS_COORDS.keys())
            # this line doesn't work
            diff1 = dirs.index(direction) - dirs.index(self.facing.name)
            if diff1 == -1 or diff1 == 3:
                self.action_queue.append(Action.TURN_LEFT)
            if diff1 == 1 or diff1 == -3:
                self.action_queue.append(Action.TURN_RIGHT)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.position = knowledge.position
        self.facing = knowledge.visible_tiles[self.position].character.facing
        self.knowledge = knowledge
        self.neighbors = self.update_neighbors()
        self.neighbors_types = self.update_neighbors_types()
        close_land = self.check_around_for("land")
        if len(self.action_queue) > 0:
            act = self.action_queue[0]
            self.action_queue.pop(0)
            return act

        if self.detect_opponent() != None:
            opponent_position = self.detect_opponent()
            self.move_to_opponent(opponent_position)
            act = self.action_queue[0]
            self.action_queue.pop(0)
            return act

        if close_land != None:
            self.move_to(close_land)
            act = self.action_queue[0]
            self.action_queue.pop(0)
            return act
        tile_to_go = random.choice(self.possible_tiles)
        self.move_to(tile_to_go)
        act = self.action_queue[0]
        self.action_queue.pop(0)
        return act

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return f"AksolotlController{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.TURQUOISE


POTENTIAL_CONTROLLERS = [
    AksolotlController("Bob"),
]
