import random
from gupb.controller.ancymon.environment import Environment
from gupb.controller.ancymon.strategies.path_finder import Path_Finder
from gupb.controller.ancymon.strategies.decision_enum import EXPLORER_DECISION
from gupb.model import characters
from gupb.model.coordinates import Coords

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


class Explore():
    def __init__(self, environment: Environment, path_finder: Path_Finder):
        self.environment: Environment = environment
        self.path_finder: Path_Finder = path_finder

        self.poi: Coords = Coords(0, 0)

        self.next_move: characters.Action = None
        self.path: list[Coords] = None

    def decide2(self) -> EXPLORER_DECISION:
        self.next_move, self.path = self.path_finder.calculate_next_move(self.environment.menhir)

        if self.next_move is None:
            while self.environment.discovered_map.get(self.poi) is not None or self.path_finder.g_score.get(
                    self.poi) == float('inf'):
                self.poi = Coords(random.randint(0, self.environment.map_known_len),
                                  random.randint(0, self.environment.map_known_len))
            self.next_move, self.path = self.path_finder.calculate_next_move(self.poi)

        if self.is_enemy_on_path():
            return EXPLORER_DECISION.ENEMY_ON_NEXT_MOVE

        return EXPLORER_DECISION.EXPLORE

    def decide(self) -> characters.Action:

        self.next_move, self.path = self.path_finder.calculate_next_move(self.environment.menhir)

        if self.next_move is None:
            while self.environment.discovered_map.get(self.poi) is not None or self.path_finder.g_score.get(self.poi) == float('inf'):
                self.poi = Coords(random.randint(0, self.environment.map_known_len),
                                  random.randint(0, self.environment.map_known_len))
            self.next_move, self.path = self.path_finder.calculate_next_move(self.poi)

        if self.next_move == characters.Action.STEP_FORWARD:
            new_position = self.environment.position + self.environment.discovered_map[
                self.environment.position].character.facing.value
            if self.environment.discovered_map[new_position].character != None:
                print("KILL WHILE EXPLORE")
                self.next_move = characters.Action.ATTACK

        return self.next_move

    def is_enemy_on_path(self) -> bool:
        if self.path and len(self.path) >= 2:
            field = self.environment.discovered_map.get(self.path[1])
            if field and field.character and field.character.controller_name != self.environment.champion.controller_name:
                return True
        return False
