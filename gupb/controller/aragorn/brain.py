from gupb.model import arenas, characters, coordinates, weapons, consumables

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.actions import *
from gupb.controller.aragorn import utils
from gupb.controller.aragorn.constants import DEBUG, INFINITY, OUR_BOT_NAME



class Brain:
    def __init__(self):
        self.memory = Memory()
        self.persistentActions = {}

        self.__initPersistentActions()
    
    def __initPersistentActions(self):
        self.persistentActions = {
            'explore': ExploreAction(),
        }

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.memory.update(knowledge)

        actions = []
        if DEBUG: dbg_ac_msgs = []

        # ------------------------------------------

        # PREVENT IDLE PENALTY

        if self.memory.willGetIdlePenalty():
            # TODO: allow to decide action, afterwards, if pos will no change - force spin
            if DEBUG: dbg_ac_msgs.append("Spinning to prevent idle penalty")
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_LEFT)
            actions.append(spinAction)
        
        # ------------------------------------------

        # DEFENDING FROM ATTACKS
        dangerousTilesDict = self.memory.map.getDangerousTilesWithDangerSourcePos(self.memory.tick, 7)

        if self.memory.position in dangerousTilesDict:
            if DEBUG: dbg_ac_msgs.append("Defending from attack")
            takeToOnesLegsAction = TakeToOnesLegsAction()
            takeToOnesLegsAction.setDangerSourcePos(dangerousTilesDict[self.memory.position])
            actions.append(takeToOnesLegsAction)
        
        # ------------------------------------------

        # ATTACKING

        if self.memory.hasOponentInRange():
            if DEBUG: dbg_ac_msgs.append("Attacking, since got oponent in range")
            attackAction = AttackAction()
            actions.append(attackAction)

        if self.memory.hasOponentOnRight():
            if DEBUG: dbg_ac_msgs.append("Attacking, since got oponent on right")
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_RIGHT)
            actions.append(spinAction)

            attackAction = AttackAction()
            actions.append(attackAction)

        if self.memory.hasOponentOnLeft():
            if DEBUG: dbg_ac_msgs.append("Attacking, since got oponent on left")
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_LEFT)
            actions.append(spinAction)

            attackAction = AttackAction()
            actions.append(attackAction)

        # ------------------------------------------

        # PICKING STUFF
        
        # potion
        [closestPotionDistance, closestPotionCoords] = self.memory.getDistanceToClosestPotion()

        if closestPotionDistance is not None and closestPotionDistance < 5:
            if DEBUG: dbg_ac_msgs.append("Picking nearby potion")
            goToPotionAction = GoToAction()
            goToPotionAction.setDestination(closestPotionCoords)
            actions.append(goToPotionAction)

        [closestWeaponDistance, closestWeaponCoords] = self.memory.getDistanceToClosestWeapon()
        
        # weapon
        if closestWeaponDistance is not None and closestWeaponDistance < 5:
            if DEBUG: dbg_ac_msgs.append("Picking nearby weapon")
            goToWeaponAction = GoToAction()
            goToWeaponAction.setDestination(closestWeaponCoords)
            actions.append(goToWeaponAction)
        
        # ------------------------------------------

        # MIST FORCED MOVEMENT

        [menhirPos, prob] = self.memory.map.menhirCalculator.approximateMenhirPos(self.memory.tick)

        if menhirPos is not None and utils.coordinatesDistance(self.memory.position, menhirPos) > self.memory.map.mist_radius / 2:
            if DEBUG: dbg_ac_msgs.append("Going closer to menhir")
            goToAroundAction = GoToAroundAction()
            goToAroundAction.setDestination(menhirPos)
            actions.append(goToAroundAction)
        
        # ------------------------------------------
        
        # Go to closest enemy
        if DEBUG: dbg_ac_msgs.append("Going closer to enemy")
        attackClosestEnemyAction = AttackClosestEnemyAction()
        actions.append(attackClosestEnemyAction)
        
        # ------------------------------------------

        # EXPLORE THE MAP

        if DEBUG: dbg_ac_msgs.append("Exploring action")
        exploreAction = self.persistentActions['explore']
        actions.append(exploreAction)

        # ------------------------------------------

        # NOTHING TO DO - JUST SPIN

        if DEBUG: dbg_ac_msgs.append("No action found, spinning")
        spinAction = SpinAction()
        actions.append(spinAction)

        # ------------------------------------------



        # ==========================================



        actionIndexPerformed = 0
        
        for action in actions:
            ret = action.perform(self.memory)
            
            if ret is not None and ret is not characters.Action.DO_NOTHING:
                if DEBUG: print("[ARAGORN|BRAIN]", action.__class__.__name__, dbg_ac_msgs[actionIndexPerformed])
                self.onDecisionReturning(ret)
                return ret
            
            if ret is None:
                if DEBUG: print("[ARAGORN|BRAIN]", "TRIED TO PERFORM ACTION BUT FAILED!", action.__class__.__name__, dbg_ac_msgs[actionIndexPerformed])
            
            actionIndexPerformed += 1
        
        if DEBUG: print("[ARAGORN|BRAIN] None of actions returned anything, spinning")
        self.onDecisionReturning(characters.Action.TURN_RIGHT)
        return characters.Action.TURN_RIGHT
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.memory.reset(arena_description)

        self.__initPersistentActions()
    
    def onDecisionReturning(self, action: characters.Action):
        if action in [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
        ]:
            self.memory.resetIdle()
