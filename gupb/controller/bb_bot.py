import random
import math

from gupb.model import arenas
from gupb.model import characters

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

class CommandInterface:
    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        pass

class DoNothingCommand(CommandInterface):
    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        return characters.Action.DO_NOTHING

class RandomCommand(CommandInterface):
    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        return random.choice(POSSIBLE_ACTIONS)

class GoToTargetCommand(CommandInterface):
    def __init__(self, controller, target):
        self.controller = controller
        self.forceGoingStrainght = False
        self.target = target
        self.prevDist = 999

    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        if(self.forceGoingStrainght == True):
            self.forceGoingStrainght = False
            return characters.Action.STEP_FORWARD
        newDist = math.dist(self.target, knowledge.position)
        delta = self.prevDist - newDist
        self.prevDist = newDist
        if (delta > 0):
            return characters.Action.STEP_FORWARD
        else:
            self.forceGoingStrainght = True
            return characters.Action.TURN_RIGHT

class ScanCommand(CommandInterface):
    def __init__(self, controller):
        self.controller = controller
        self.iteration = 0
        self.scanResults = {}


    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.scanResults.update(knowledge.visible_tiles)
        self.iteration += 1
        if (self.iteration == 4):
            target = None
            for (key, value) in self.scanResults.items():
                if(value.type == 'menhir'):
                    self.controller.currentCommand = GoToTargetCommand(self.controller, key)
                    return characters.Action.DO_NOTHING
            self.controller.currentCommand = RandomCommand()
        return characters.Action.TURN_RIGHT

# class DIRECTIONS:
#     NORTH = 0,
#     EAST = 1,
#     SOUTH = 2,
#     WEST = 3

# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BBBotController:    
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.currentCommand = ScanCommand(self)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BBBotController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.currentCommand.decide(knowledge)

    @property
    def name(self) -> str:
        return f'BBBotController{self.first_name}'


POTENTIAL_CONTROLLERS = [
    BBBotController("Bartek"),
]
