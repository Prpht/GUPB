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
class Hunter():
    def __init__(self, environment: Environment, path_finder: Path_Finder):
        self.environment: Environment = environment
        self.path_finder: Path_Finder = path_finder
        self.poi: Coords = Coords(0, 0)
        self.next_target = None
        self.next_target_coord: Coords = None

    def decide(self)-> characters.Action:
        if self.is_enemy_neer() and (self.environment.enemies_left >= self.environment.enemies_num * 0.6 or self.is_menhir_neer()):
            # print(self.next_target)

            next_move_to_atack = self.path_finder.caluclate(self.environment.position, self.next_target_coord)

            sub = self.environment.position - self.next_target_coord

            if(next_move_to_atack == characters.Action.STEP_FORWARD and abs(sub.x + sub.y) == 1 and (sub.x == 0 or sub.y == 0)):
                return characters.Action.ATTACK

            return next_move_to_atack
        return None


    def is_menhir_neer(self):
        if self.environment.menhir != None:
            margin = self.environment.enemies_left - 2
            if len(self.environment.discovered_map[self.environment.position].effects) > 0:
                margin = 0
            return (abs(self.environment.menhir[0] - self.environment.position.x) < margin and
                    abs(self.environment.menhir[1] - self.environment.position.y) < margin)

    def is_enemy_neer(self, size_of_searched_area: int = 2):
        for x in range(-size_of_searched_area, size_of_searched_area + 1):
            for y in range(-size_of_searched_area, size_of_searched_area + 1):
                field = self.environment.discovered_map.get(self.environment.position + Coords(x, y))
                if field != None and field.character != None and field.character.controller_name != self.environment.champion.controller_name:
                    # if field.character.health <= self.environment.champion.health:
                    self.next_target = field.character
                    self.next_target_coord = Coords(x, y) + self.environment.position
                    return True
        self.next_target = None
        self.next_target_coord = None
        return False