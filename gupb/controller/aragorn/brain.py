from gupb.model import arenas, characters, coordinates, weapons

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.actions import *
from gupb.controller.aragorn import utils
from gupb.controller.aragorn.constants import DEBUG, INFINITY, OUR_BOT_NAME



class Brain:
    def __init__(self):
        self.memory = Memory()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.memory.update(knowledge)

        actions = []
        if DEBUG: dbg_ac_msgs = []

        if self.memory.willGetIdlePenalty():
            # TODO: allow to decide action, afterwards, if pos will no change - force spin
            if DEBUG: dbg_ac_msgs.append("Spinning to prevent idle penalty")
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_LEFT)
            actions.append(spinAction)

        # ATTACKING

        if self.memory.hasOponentInFront():
            if DEBUG: dbg_ac_msgs.append("Attacking, since got oponent in front")
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

        if closestPotionDistance is not None and closestPotionDistance < 8:
            if DEBUG: dbg_ac_msgs.append("Picking nearby potion")
            goToPotionAction = GoToAction()
            goToPotionAction.setDestination(closestPotionCoords)
            actions.append(goToPotionAction)

        [closestWeaponDistance, closestWeaponCoords] = self.memory.getDistanceToClosestWeapon()
        
        # weapon
        if closestWeaponDistance is not None and closestWeaponDistance < 8:
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

        closestEnemy = None
        closestEnemyDistance = INFINITY

        for coords in self.memory.map.terrain:
            if (
                self.memory.map.terrain[coords].character is not None
                and self.memory.map.terrain[coords].character.controller_name != OUR_BOT_NAME
                and self.memory.position != coords
            ):
                distance = utils.coordinatesDistance(self.memory.position, coords)
                
                if distance < closestEnemyDistance:
                    closestEnemy = coords
                    closestEnemyDistance = distance
        
        if closestEnemy is not None:
            if DEBUG: dbg_ac_msgs.append("Going closer to enemy")
            goToAttackAction = GoToAroundAction()
            goToAttackAction.setDestination(closestEnemy)
            actions.append(goToAttackAction)

        if DEBUG: dbg_ac_msgs.append("No action found, spinning")
        spinAction = SpinAction()
        actions.append(spinAction)
        
        # ------------------------------------------
        
        actionIndexPerformed = 0
        
        for action in actions:
            ret = action.perform(self.memory)
            
            if ret is not None and ret is not characters.Action.DO_NOTHING:
                if DEBUG: print("[ARAGORN|BRAIN]", action.__class__.__name__, dbg_ac_msgs[actionIndexPerformed])
                self.onDecisionReturning(ret)
                return ret
            
            actionIndexPerformed += 1
        
        if DEBUG: print("[ARAGORN|BRAIN] None of actions returned anything, spinning")
        self.onDecisionReturning(characters.Action.TURN_RIGHT)
        return characters.Action.TURN_RIGHT
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.memory.reset(arena_description)
    
    def onDecisionReturning(self, action: characters.Action):
        if action in [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
        ]:
            self.memory.resetIdle()
