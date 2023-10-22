from gupb.model import arenas, coordinates, weapons
from gupb.model import characters

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.actions import *



class Brain:
    def __init__(self):
        self.memory = Memory()
        self.actions = {
            'spin': SpinAction(),
            'go_to': GoToAction(),
            'random': RandomAction(),
            'attack': AttackAction(),
        }
        self.state = 0

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.memory.update(knowledge)

        actions = []
        dstFacing = None


        # ---

        if self.memory.willGetIdlePenalty():
            spinAction = self.actions['spin']
            spinAction.setSpin(characters.Action.TURN_LEFT)
            actions.append(spinAction)

        if self.memory.hasOponentInFront():
            attackAction = self.actions['attack']
            actions.append(attackAction)
        
        [closestPotionDistance, closestPotionCoords] = self.memory.getDistanceToClosestPotion()
        
        if closestPotionDistance is not None and closestPotionDistance < 5:
            goToPotionAction = GoToAction()
            goToPotionAction.setDestination(closestPotionCoords)
            actions.append(goToPotionAction)

        # ---

        if self.state == 0:
            # go to pick up a sword
            dstPos = self.memory.map.getWeaponPos(weapons.Sword)
            attackAction = False

            if dstPos == self.memory.position:
                self.state += 1
        
        if self.state == 1:
            # go to camping spot
            [dstPos, dstFacing] = self.memory.map.hidingSpot
            attackAction = False

            if dstPos == self.memory.position and dstFacing == self.memory.facing:
                self.state += 1
        
        if self.state == 2:
            # continously attack
            [tmp_dstPos, tmp_dstFacing] = self.memory.map.hidingSpot
            
            if self.memory.facing != tmp_dstFacing:
                dstPos = tmp_dstPos
                dstFacing = tmp_dstFacing
                attackAction = False
            else:
                dstPos = None
                attackAction = True

            # if mist is comming - go to the next stage
            if self.memory.map.mist_radius < self.memory.map.size[0] * 4 / 5:
                self.state += 1
        
        if self.state >= 3:
            # go to map center
            dstPos = self.memory.map.passableCenter
            attackAction = False

            if dstPos == self.memory.position:
                self.state += 1

        if dstPos is not None:
            goToAction = self.actions['go_to']
            goToAction.setDestination(dstPos)
            if dstFacing is not None:
                goToAction.setDestinationFacing(dstFacing)
            actions.append(goToAction)
        
        if attackAction:
            attackAction = self.actions['attack']
            actions.append(attackAction)

        spinAction = self.actions['spin']
        actions.append(spinAction)
        
        for action in actions:
            ret = action.perform(self.memory)
            
            if ret is not None and ret is not characters.Action.DO_NOTHING:
                self.onDecisionReturning(ret)
                return ret
        
        self.onDecisionReturning(characters.Action.TURN_RIGHT)
        return characters.Action.TURN_RIGHT
    
    def onDecisionReturning(self, action: characters.Action):
        # print(action)
        if action in [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
        ]:
            self.memory.resetIdle()
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.memory.reset(arena_description)
