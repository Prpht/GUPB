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

POSSIBLE_ACTIONS2 = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
]

TABARD_ASSIGNMENT = {
    "Alice": characters.Tabard.BLUE,
    "Bob": characters.Tabard.YELLOW,
    "Cecilia": characters.Tabard.RED,
    "Darius": characters.Tabard.GREY,
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.cached_enemy_coords = None
        self.facing = None
        self.facing_word = None
        self.counter = 0
        self.old_coords = None
        self.old_facing = None
    def __eq__(self, other: object) -> bool:
        if isinstance(other, BotController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        
        fields = knowledge[1]
        enemy_coords = None
        
        for key in fields:
            char = fields[key][2]
            if char != None and char[0] != "BotControllerAlice":
                enemy_coords = key
                self.cached_enemy_coords = enemy_coords
                break
                
            if char != None and char[0] == "BotControllerAlice":
                self.facing = char.facing.value
                self.facing_word = char[3]
        
        combat = False
        if enemy_coords != None:
            if (knowledge[0][0] + self.facing[0] == enemy_coords[0] and knowledge[0][1] + self.facing[1] == enemy_coords[1]):
                combat = True
                
        if (self.old_coords == knowledge[0] and self.old_facing == self.facing and combat == False):
            self.counter = 3
            

            
        self.old_coords = knowledge[0]
        self.old_facing = self.facing

        if self.cached_enemy_coords == None:
            return random.choice(POSSIBLE_ACTIONS2)
            
        if combat == True:
            return characters.Action.ATTACK

        if self.cached_enemy_coords != None and self.counter > 0:
            self.counter = self.counter - 1
            return random.choice(POSSIBLE_ACTIONS2)

        if self.cached_enemy_coords != None:

            x = self.cached_enemy_coords[0]-knowledge[0][0]
            y = self.cached_enemy_coords[1]-knowledge[0][1]
            
            angle1 = math.atan2(y,x)
            angle2 = math.atan2(self.facing[1],self.facing[0])
            
            angle3 = angle2 - angle1
            if (angle3 > math.pi): angle3 = angle3 - 2*math.pi
            angle3 *= 57.3
            if (angle3 < -46): 
                return characters.Action.TURN_RIGHT
 
            if angle3 > 46: 
                return characters.Action.TURN_LEFT
            return characters.Action.STEP_FORWARD

    @property
    def name(self) -> str:
        return f'BotController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return TABARD_ASSIGNMENT[self.first_name] if self.first_name in TABARD_ASSIGNMENT else characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    BotController("Alice"),
    BotController("Bob"),
    BotController("Cecilia"),
    BotController("Darius"),
]
