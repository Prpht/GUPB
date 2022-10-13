import random
from typing import  List

from gupb import controller
from gupb.model import arenas, characters, coordinates

from queue import Queue
from collections import defaultdict
from gupb.controller.lord_icon.distance import astar, dist, Point2d, Direction
from gupb.model.arenas import Arena
import numpy as np

from gupb.model.weapons import WeaponDescription

mapper = defaultdict(lambda: 1)
mapper["land"] = 0
mapper["menhir"] = 0

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


class LordIcon(controller.Controller):
    def __init__(self, first_name: str) -> None:
        self.arena = Arena.load('lone_sanctum')
        self.first_name: str = first_name
        self.moves_q = Queue()
        self.map = np.ones((19, 19))
        self.position = (0, 0)
        self.facing = 0
        self.attack = False
        self.directions = [
            (0, -1), # lewo
            (-1, 0), # góra
            (0, 1), # prawo
            (1, 0), # dół
        ]
        self.safe_position = (9, 8)
        self.menhir = coordinates.Coords(9, 9)
        self.current_direction = None
        self.previous_pos = (0, 0)
        self.previous_move = characters.Action.DO_NOTHING
        self.has_weapon = False
        self.weapon_positions = [(1, 1), (1,2), (2,1)]
        self.destination = self.weapon_positions[0]

        for key, value in self.arena.terrain.items():
            self.map[key.y][key.x] = mapper[value.description().type]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LordIcon):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def update_map(self, knowledge: characters.ChampionKnowledge):
        for coord, tile in knowledge.visible_tiles.items():
            y, x = (
                (coord.x, coord.y)
                if isinstance(coord, coordinates.Coords)
                else (coord[0], coord[1])
            )
            _dist = dist(self.position, (x, y))
            if _dist == 1:
                self.facing = self.directions.index(
                    (x - self.position[0], y - self.position[1])
                )
                if tile.character:
                    self.attack = True
                    return
            self.attack = False
            self.map[x, y] = mapper[tile.type]
            if (x, y) == self.weapon_positions[0] and tile.loot.name != 'axe':
                self.weapon_positions.pop(0)

    def go_to_destination(self, destination: Point2d):
        moves_todo = astar(
            self.map,
            self.position,
            destination,
        )
        if moves_todo:
            self.empty_queue()
            self.process_moves(moves_todo)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.position = (knowledge.position.y, knowledge.position.x)
        self.update_map(knowledge)

        if self.position in self.weapon_positions:
            self.has_weapon = True

        if self.position == self.safe_position and self.has_weapon:
            return random.choices(POSSIBLE_ACTIONS, weights=(1, 0, 0, 1), k=1)[0]

        if self.attack:
            return characters.Action.ATTACK

        if self.has_weapon:
            self.destination = self.safe_position

        self.go_to_destination(self.destination)

        if len(self.weapon_positions) == 0:
            self.destination = self.menhir
        else:
            self.destination = self.weapon_positions[0]

        if self.moves_q.empty():
            return random.choices(POSSIBLE_ACTIONS, weights=(1, 1, 3, 1), k=1)[0]
        else:
            action = self.moves_q.get()
            self.previous_move = action
            return action

    def process_moves(self, points: List[Point2d]) -> None:
        if not points:
            return

        self.current_direction = points[-1]

        position = self.position
        for point in points:
            self.move_to(point)
            self.position = point

        self.position = position

    def move_to(self, where: Direction) -> None:
        if self.position == where:
            return

        direction = (where[0] - self.position[0], where[1] - self.position[1])
        self.rotate(direction)
        self.moves_q.put(characters.Action.STEP_FORWARD)

    def rotate(self, where: Direction) -> None:
        if self.facing is None:
            return

        if self.direction == where:
            return

        if where not in self.directions:
            return

        where_idx = self.directions.index(where)
        diff = self.facing - where_idx
        if abs(diff) == 2:
            self.moves_q.put(characters.Action.TURN_LEFT)
            self.moves_q.put(characters.Action.TURN_LEFT)
        elif diff in [1, -3]:
            self.moves_q.put(characters.Action.TURN_LEFT)
        elif diff in [-1, 3]:
            self.moves_q.put(characters.Action.TURN_RIGHT)

        self.facing = where_idx

    def empty_queue(self):
        self.moves_q.queue.clear()

    def do_circle(self):
        for _ in range(4):
            self.moves_q.put(characters.Action.TURN_RIGHT)

    @property
    def direction(self) -> Direction:
        return self.directions[self.facing]

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.moves_q = Queue()
        self.position = (0, 0)
        self.facing = 0
        self.menhir = None
        self.current_direction = None
        self.previous_pos = (0, 0)
        self.previous_move = characters.Action.DO_NOTHING
        self.has_weapon = False

    @property
    def name(self) -> str:
        return f"RandomController{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.YELLOW
