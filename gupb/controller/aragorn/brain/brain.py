from gupb.model import arenas, characters, coordinates, weapons, consumables
from gupb.model.profiling import profile

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.actions import *
from .strategy import *
from gupb.controller.aragorn import utils
from gupb.controller.aragorn import pathfinding
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY, OUR_BOT_NAME

import time

class Brain:
    def __init__(self):
        self.memory = Memory()
        self.persistentActions = {}

        self._init_persistent_actions()
        self._init_strategies()
        self.wholeTime = 0
        self.state = 0
    
    def _init_persistent_actions(self):
        self.persistentActions = {
            'explore': AdvancedExploreAction(),
        }
    
    def _init_strategies(self):
        self.strategies = {
            0: StrategyOpening(self),
            1: StrategyMidgame(self),
            2: StrategyEndgame(self),
        }

    def update_state(self):
        if self.state == 0:
            if self.memory.tick > 10:
                self.state = 1
            else:
                currentWeaponDescription = self.memory.getCurrentWeaponDescription()
                [closestWeaponDistance, closestWeaponCoords] = self.memory.getDistanceToClosestWeapon()
                if closestWeaponDistance > 10:
                    self.state = 1
                if currentWeaponDescription is not None and currentWeaponDescription.name != 'knife':
                    self.state = 1
        elif self.state == 1:
            if self.memory.map.mist_radius < self.memory.map.size[0] * 4/5:
                [menhirPos, prob] = self.memory.map.menhirCalculator.approximateMenhirPos(self.memory.tick)
                if prob == 1:
                    self.state = 2
            if self.memory.health >= 16:
                self.state = 2
    
    @profile
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if DEBUG: print()
        if DEBUG: print("[ARAGORN|BRAIN] Deciding... (is in state", self.state, ")")

        actionIndexPerformed = 0

        # update memory

        self.memory.update(knowledge)

        # update state
        
        self.update_state()

        # select actions depending on state
        
        strategyNumber = self.state
        
        if strategyNumber in self.strategies:
            strategy: Strategy = self.strategies[strategyNumber]
        else:
            strategy: Strategy = Strategy()

        
        # pick action & perform it

        if DEBUG: print("[ARAGORN|BRAIN] State=", self.state)

        for action, dbg_ac_msg in strategy.prepare_actions():
            if action is None:
                continue
            startTime = time.time()
            ret = action.perform(self.memory)
            endTime = time.time()
            self.wholeTime += endTime - startTime
            
            if ret is not None and ret is not characters.Action.DO_NOTHING:
                if DEBUG: print("[ARAGORN|BRAIN]", action.__class__.__name__, dbg_ac_msg)
                self.on_decision_returning(ret)
                
                return ret
            
            # if ret is None:
            #     if DEBUG: print("[ARAGORN|BRAIN]", "TRIED TO PERFORM ACTION BUT FAILED!", action.__class__.__name__, dbg_ac_msg)
            
            actionIndexPerformed += 1
        
        if DEBUG: print("[ARAGORN|BRAIN] None of actions returned anything, spinning")
        self.on_decision_returning(characters.Action.TURN_RIGHT)
        
        return characters.Action.TURN_RIGHT
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.memory.reset(arena_description)
        pathfinding.invalidate_PF_cache()
        self.state = 0

        self._init_persistent_actions()
        self._init_strategies()
    
    def on_decision_returning(self, action: characters.Action):
        if action in [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
            characters.Action.STEP_BACKWARD,
            characters.Action.STEP_LEFT,
            characters.Action.STEP_RIGHT,
        ]:
            self.memory.resetIdle()
        
        self.memory.addLastAction(action)
