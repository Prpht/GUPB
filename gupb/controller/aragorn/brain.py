from gupb.model import arenas, characters, coordinates, weapons

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.actions import *
from gupb.controller.aragorn import utils
from gupb.controller.aragorn.constants import DEBUG, INFINITY



class Brain:
    def __init__(self):
        self.memory = Memory()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.memory.update(knowledge)

        actions = []

        if self.memory.willGetIdlePenalty():
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_LEFT)
            actions.append(spinAction)

        if self.memory.hasOponentInFront():
            attackAction = AttackAction()
            actions.append(attackAction)

        if self.memory.hasOponentOnRight():
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_RIGHT)
            actions.append(spinAction)

            attackAction = AttackAction()
            actions.append(attackAction)

        if self.memory.hasOponentOnLeft():
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_LEFT)
            actions.append(spinAction)

            attackAction = AttackAction()
            actions.append(attackAction)

        [closestPotionDistance, closestPotionCoords] = self.memory.getDistanceToClosestPotion()

        if closestPotionDistance is not None and closestPotionDistance < 8:
            goToPotionAction = GoToAction()
            goToPotionAction.setDestination(closestPotionCoords)
            actions.append(goToPotionAction)

        [closestWeaponDistance, closestWeaponCoords] = self.memory.getDistanceToClosestWeapon()

        if closestWeaponDistance is not None and closestWeaponDistance < 8:
            goToWeaponAction = GoToAction()
            goToWeaponAction.setDestination(closestWeaponCoords)
            actions.append(goToWeaponAction)
                
        [menhirPos, prob] = self.memory.map.menhirCalculator.approximateMenhirPos(self.memory.tick)

        if menhirPos is not None and utils.coordinatesDistance(self.memory.position, menhirPos) > self.memory.map.mist_radius / 2:
            goToAroundAction = GoToAroundAction()
            goToAroundAction.setDestination(menhirPos)
            actions.append(goToAroundAction)
        
        closestEnemy = None
        closestEnemyDistance = INFINITY

        for coords in self.memory.map.terrain:
            if self.memory.map.terrain[coords].character is not None and self.memory.position != coords:
                distance = utils.coordinatesDistance(self.memory.position, coords)
                
                if distance < closestEnemyDistance:
                    closestEnemy = coords
                    closestEnemyDistance = distance
        
        if closestEnemy is not None:
            goToAttackAction = GoToAroundAction()
            goToAttackAction.setDestination(closestEnemy)
            actions.append(goToAttackAction)

        
        spinAction = SpinAction()
        actions.append(spinAction)
        
        for action in actions:
            ret = action.perform(self.memory)
            
            if ret is not None and ret is not characters.Action.DO_NOTHING:
                self.onDecisionReturning(ret)
                return ret
        
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
