import random
from gupb.controller.ancymon.environment import Environment
from gupb.controller.ancymon.strategies.path_finder import Path_Finder
from gupb.controller.ancymon.strategies.decision_enum import EXPLORER_DECISION
from gupb.model import characters
from gupb.model.coordinates import Coords


class Explore():
    def __init__(self, environment: Environment):
        self.environment: Environment = environment
        self.path_finder: Path_Finder = None

        self.next_move: characters.Action = None
        self.path: list[Coords] = None

    def decide(self, path_finder: Path_Finder) -> EXPLORER_DECISION:
        self.path_finder = path_finder

        self.next_move, self.path = None, None

        if self.environment.mist_seen is True:
            self.next_move, self.path = self.path_finder.calculate_next_move(self.environment.menhir)
            if self.path_finder.avoid_obstacles:
                return EXPLORER_DECISION.NO_ALTERNATIVE_PATH
        i = 0

        if self.next_move is None:
            while (i < 2 * self.environment.map_known_len) and (self.environment.discovered_map.get(
                    self.environment.poi) is not None or self.path_finder.g_score.get(self.environment.poi) == float('inf')):
                i += 1
                self.environment.poi = Coords(random.randint(0, self.environment.map_known_len),
                                              random.randint(0, self.environment.map_known_len))
            self.next_move, self.path = self.path_finder.calculate_next_move(self.environment.poi)

        if self.next_move is None or self.path is None:
            # print('Explorer Alternate path case')
            return EXPLORER_DECISION.NO_ALTERNATIVE_PATH

        if self.is_enemy_on_path():
            return EXPLORER_DECISION.ENEMY_ON_NEXT_MOVE

        return EXPLORER_DECISION.EXPLORE

    def is_enemy_on_path(self) -> bool:
        if self.path and len(self.path) >= 2:
            field = self.environment.discovered_map.get(self.path[1])
            if field and field.character and field.character.controller_name != self.environment.champion.controller_name:
                return True
        return False
