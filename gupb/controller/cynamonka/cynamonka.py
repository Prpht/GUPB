import heapq
import math
from re import S
import traceback
import random
from typing import Dict
from gupb import controller
from gupb.model import arenas, effects, tiles
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import weapons
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife, Axe, Bow, Sword, Amulet
from gupb.controller.cynamonka.brain import Map, Decider

"""
NAJNOWSZA KONFIGURACJA Z UCIEKANIEM, mojas
"""
POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
]





TerrainDescription = Dict[Coords, tiles.TileDescription]

class CynamonkaController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.decider = Decider()
        
        

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CynamonkaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.decider.find_the_best_action(knowledge)

    def praise(self, score: int) -> None:
        pass

    def reset(self,  game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.decider.reset(arena_description)
    
    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK


   