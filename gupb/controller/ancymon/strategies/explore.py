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
            end = Coords(self.environment.menhir[0], self.environment.menhir[1])
        else:
            end = self.poi

        path = self.path_finder.caluclate(start, end)

        if path == None or len(path) == 1 or self.environment.discovered_map.get(self.poi) != None: #Unexpected move
            self.poi = Coords(random.randint(0, self.environment.map_known_len),
                              random.randint(0, self.environment.map_known_len))
            while (self.environment.discovered_map.get(self.poi) != None):
                self.poi = Coords(random.randint(0, self.environment.map_known_len),
                                  random.randint(0, self.environment.map_known_len))
            return random.choice([characters.Action.TURN_RIGHT, characters.Action.TURN_LEFT])

        next_move = path[1]
        move_vector = next_move - start
        sub = self.environment.discovered_map[start].character.facing.value - move_vector

        if sub.x != 0 or sub.y != 0:
            if sub.x == 2 or sub.y == 2 or sub.x == -2 or sub.y == -2:
                return characters.Action.TURN_RIGHT

            if move_vector.x == 0:
                if sub.x * sub.y == 1:
                    return characters.Action.TURN_LEFT
                else:
                    return characters.Action.TURN_RIGHT

            if move_vector.y == 0:
                if sub.x * sub.y == 1:
                    return characters.Action.TURN_RIGHT
                else:
                    return characters.Action.TURN_LEFT

        #Move forward

        return characters.Action.STEP_FORWARD
