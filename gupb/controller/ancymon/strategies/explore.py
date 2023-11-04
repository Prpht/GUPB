import random
from gupb.controller.ancymon.environment import Environment
from gupb.controller.ancymon.strategies.path_finder import Path_Finder
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

    def decide(self) -> characters.Action:
        start = self.environment.position

        if self.environment.menhir != None:
            end = self.environment.menhir
        else:
            end = self.poi

        next_move = self.path_finder.caluclate(start, end)

        if next_move == None or self.environment.discovered_map.get(self.poi) != None:
            self.poi = Coords(random.randint(0, self.environment.map_known_len),
                              random.randint(0, self.environment.map_known_len))
            while (self.environment.discovered_map.get(self.poi) != None):
                self.poi = Coords(random.randint(0, self.environment.map_known_len),
                                  random.randint(0, self.environment.map_known_len))
            return None

        if next_move == characters.Action.STEP_FORWARD:
            new_position = self.environment.position + self.environment.discovered_map[self.environment.position].character.facing.value
            if self.environment.discovered_map[new_position].character != None:
                # print("KILL WHILE EXPLORE")
                next_move = characters.Action.ATTACK

        return next_move


