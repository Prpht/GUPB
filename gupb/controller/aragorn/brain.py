from gupb.model import arenas, characters, coordinates, weapons, consumables

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.actions import *
from gupb.controller.aragorn import utils
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY, OUR_BOT_NAME
from gupb.model.profiling import profile

import time

class Brain:
    def __init__(self):
        self.memory = Memory()
        self.persistentActions = {}

        self.__initPersistentActions()
        self.wholeTime = 0
        self.state = 1
    
    def __initPersistentActions(self):
        self.persistentActions = {
            'explore': AdvancedExploreAction(),
        }

    def prepareActionsOpening(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.memory.update(knowledge)

        # ------------------------------------------
        
        dangerousTilesDict = self.memory.map.getDangerousTilesWithDangerSourcePos(self.memory.tick, 7)

        # ------------------------------------------

        # PREVENT IDLE PENALTY

        if self.memory.willGetIdlePenalty():
            # TODO: allow to decide action, afterwards, if pos will no change - force spin
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_LEFT)
            yield spinAction, "Spinning to prevent idle penalty"
        
        # ------------------------------------------

        # DEFENDING FROM ATTACKS

        if self.memory.position in dangerousTilesDict:
            takeToOnesLegsAction = TakeToOnesLegsAction()
            takeToOnesLegsAction.setDangerSourcePos(dangerousTilesDict[self.memory.position])
            yield takeToOnesLegsAction, "Defending from attack"
        
        # ------------------------------------------

        # PICKING UP POTION

        [closestPotionDistance, closestPotionCoords] = self.memory.getDistanceToClosestPotion(5)

        if DEBUG2: print("[ARAGORN|BRAIN] closestPotionDistance", closestPotionDistance, "closestPotionCoords", closestPotionCoords)

        if closestPotionDistance is not None and closestPotionDistance < 5:
            goToPotionAction = GoToAction()
            goToPotionAction.setDestination(closestPotionCoords)
            goToPotionAction.setUseAllMovements(True)
            goToPotionAction.setAllowDangerous(True)
            yield goToPotionAction, "Picking nearby potion"

        # ------------------------------------------
        
        # PICKING UP WEAPON

        [closestWeaponDistance, closestWeaponCoords] = self.memory.getDistanceToClosestWeapon()

        if DEBUG2: print("[ARAGORN|BRAIN] closestWeaponDistance", closestWeaponDistance, "closestWeaponCoords", closestWeaponCoords)

        if closestWeaponCoords is not None:
            goToWeaponAction = GoToAroundAction()
            goToWeaponAction.setDestination(closestWeaponCoords)
            yield goToWeaponAction, "Picking nearby weapon"
        else:
            if DEBUG2: print("[ARAGORN|BRAIN] No weapon found")
        
        # ------------------------------------------
        
        # ROTATE TO SEE MORE

        seeMoreAction = SeeMoreAction()
        yield seeMoreAction, "Rotating to see more"

        # ------------------------------------------

        # NOTHING TO DO - JUST SPIN

        spinAction = SpinAction()
        yield spinAction, "No action found, spinning"

        # ==========================================

    def prepareActionsMidGame(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.memory.update(knowledge)

        # ------------------------------------------
        
        dangerousTilesDict = self.memory.map.getDangerousTilesWithDangerSourcePos(self.memory.tick, 7)

        # ------------------------------------------

        # PREVENT IDLE PENALTY

        if self.memory.willGetIdlePenalty():
            # TODO: allow to decide action, afterwards, if pos will no change - force spin
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_LEFT)
            yield spinAction, "Spinning to prevent idle penalty"
        
        # ------------------------------------------

        # DEFENDING FROM ATTACKS

        if self.memory.position in dangerousTilesDict:
            takeToOnesLegsAction = TakeToOnesLegsAction()
            takeToOnesLegsAction.setDangerSourcePos(dangerousTilesDict[self.memory.position])
            yield takeToOnesLegsAction, "Defending from attack"
        
        # ------------------------------------------

        # PICKING UP POTION

        [closestPotionDistance, closestPotionCoords] = self.memory.getDistanceToClosestPotion(5)

        if DEBUG2: print("[ARAGORN|BRAIN] closestPotionDistance", closestPotionDistance, "closestPotionCoords", closestPotionCoords)

        if closestPotionDistance is not None and closestPotionDistance < 5:
            goToPotionAction = GoToAction()
            goToPotionAction.setDestination(closestPotionCoords)
            goToPotionAction.setUseAllMovements(True)
            goToPotionAction.setAllowDangerous(True)
            yield goToPotionAction, "Picking nearby potion"

        # ------------------------------------------
        
        # ATTACKING

        oponentInRange = self.memory.getClosestOponentInRange()

        if DEBUG2: print("[ARAGORN|BRAIN] oponentInRange", oponentInRange, "is on safe tile:", self.memory.position not in dangerousTilesDict.keys(), "oppo health:", oponentInRange.health if oponentInRange is not None else None, "my health:", self.memory.health)

        if (
            oponentInRange is not None
            and (
                self.memory.position not in dangerousTilesDict.keys()
                or (
                    oponentInRange.health <= self.memory.health
                    and oponentInRange.health <= consumables.POTION_RESTORED_HP
                )
            )
        ):
            attackAction = AttackAction()
            yield attackAction, "Attacking, since got oponent in range"
        
        # ------------------------------------------

        # MIST FORCED MOVEMENT

        [menhirPos, prob] = self.memory.map.menhirCalculator.approximateMenhirPos(self.memory.tick)

        if DEBUG2: print("[ARAGORN|BRAIN] menhirPos", menhirPos, "prob", prob)
        
        if menhirPos is not None:
            goCloserToMenhir = False

            if self.memory.map.mist_radius < 7:
                goCloserToMenhir = True
            
            if not goCloserToMenhir:
                dist = pathfinding.get_path_cost(self.memory, self.memory.position, menhirPos, self.memory.facing, True)

                if dist is None or dist == INFINITY:
                    dist = utils.manhattanDistance(self.memory.position, menhirPos)
                
                if dist >= self.memory.map.mist_radius - 5:
                    goCloserToMenhir = True

            if goCloserToMenhir:
                goToAroundAction = GoToAroundAction()
                goToAroundAction.setDestination(menhirPos)
                goToAroundAction.setAllowDangerous(True)
                goToAroundAction.setUseAllMovements(True)
                yield goToAroundAction, "Going closer to menhir"

        # ------------------------------------------
        
        # PICKING UP WEAPON

        [closestWeaponDistance, closestWeaponCoords] = self.memory.getDistanceToClosestWeapon()

        if DEBUG2: print("[ARAGORN|BRAIN] closestWeaponDistance", closestWeaponDistance, "closestWeaponCoords", closestWeaponCoords)

        if closestWeaponCoords is not None and closestWeaponDistance < 15:
            goToWeaponAction = GoToAction()
            goToWeaponAction.setDestination(closestWeaponCoords)
            yield goToWeaponAction, "Picking nearby weapon"
        
        # ------------------------------------------
        
        # ROTATE TO SEE MORE

        seeMoreAction = SeeMoreAction()
        yield seeMoreAction, "Rotating to see more"

        # ------------------------------------------

        # RAGE ATTACK

        rageAttackAction = RageAttackAction()
        yield rageAttackAction, "Rage attack"
        
        # Go to closest enemy
        attackClosestEnemyAction = AttackClosestEnemyAction()
        yield attackClosestEnemyAction, "Going closer to enemy"

        # ------------------------------------------

        # EXPLORE THE MAP

        exploreAction = self.persistentActions['explore']
        yield exploreAction, "Exploring action"

        # ------------------------------------------

        # NOTHING TO DO - JUST SPIN

        spinAction = SpinAction()
        yield spinAction, "No action found, spinning"

        # ==========================================

    def prepareActionsEndGame(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.memory.update(knowledge)

        # ------------------------------------------
        
        dangerousTilesDict = self.memory.map.getDangerousTilesWithDangerSourcePos(self.memory.tick, 7)

        # ------------------------------------------

        # PREVENT IDLE PENALTY

        if self.memory.willGetIdlePenalty():
            # TODO: allow to decide action, afterwards, if pos will no change - force spin
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_LEFT)
            yield spinAction, "Spinning to prevent idle penalty"
        
        # ------------------------------------------

        # DEFENDING FROM ATTACKS

        if self.memory.position in dangerousTilesDict:
            takeToOnesLegsAction = TakeToOnesLegsAction()
            takeToOnesLegsAction.setDangerSourcePos(dangerousTilesDict[self.memory.position])
            yield takeToOnesLegsAction, "Defending from attack"
        
        # ------------------------------------------

        # PICKING UP POTION

        [closestPotionDistance, closestPotionCoords] = self.memory.getDistanceToClosestPotion(5)

        if DEBUG2: print("[ARAGORN|BRAIN] closestPotionDistance", closestPotionDistance, "closestPotionCoords", closestPotionCoords)

        if closestPotionDistance is not None and closestPotionDistance < 5:
            goToPotionAction = GoToAction()
            goToPotionAction.setDestination(closestPotionCoords)
            goToPotionAction.setUseAllMovements(True)
            goToPotionAction.setAllowDangerous(True)
            yield goToPotionAction, "Picking nearby potion"

        # ------------------------------------------
        
        # ATTACKING

        oponentInRange = self.memory.getClosestOponentInRange()

        if DEBUG2: print("[ARAGORN|BRAIN] oponentInRange", oponentInRange, "is on safe tile:", self.memory.position not in dangerousTilesDict.keys(), "oppo health:", oponentInRange.health if oponentInRange is not None else None, "my health:", self.memory.health)

        if (
            oponentInRange is not None
            and (
                self.memory.position not in dangerousTilesDict.keys()
                or (
                    oponentInRange.health <= self.memory.health
                    and oponentInRange.health <= consumables.POTION_RESTORED_HP
                )
            )
        ):
            attackAction = AttackAction()
            yield attackAction, "Attacking, since got oponent in range"
        
        # ------------------------------------------

        # MIST FORCED MOVEMENT

        [menhirPos, prob] = self.memory.map.menhirCalculator.approximateMenhirPos(self.memory.tick)
        distanceToMenhir = None

        if DEBUG2: print("[ARAGORN|BRAIN] menhirPos", menhirPos, "prob", prob)
        
        if menhirPos is not None:
            goCloserToMenhir = False
            
            if not goCloserToMenhir:
                distanceToMenhir = pathfinding.get_path_cost(self.memory, self.memory.position, menhirPos, self.memory.facing, True)

                if distanceToMenhir is None or distanceToMenhir == INFINITY:
                    distanceToMenhir = utils.manhattanDistance(self.memory.position, menhirPos)

                if distanceToMenhir >= self.memory.map.mist_radius - 1:
                    goCloserToMenhir = True

            if goCloserToMenhir:
                goToAroundAction = GoToAroundAction()
                goToAroundAction.setDestination(menhirPos)
                goToAroundAction.setAllowDangerous(True)
                goToAroundAction.setUseAllMovements(True)
                yield goToAroundAction, "Going closer to menhir"

        # ------------------------------------------
        
        # PICKING UP WEAPON

        [closestWeaponDistance, closestWeaponCoords] = self.memory.getDistanceToClosestWeapon()

        if DEBUG2: print("[ARAGORN|BRAIN] closestWeaponDistance", closestWeaponDistance, "closestWeaponCoords", closestWeaponCoords)

        if closestWeaponCoords is not None and closestWeaponDistance < 5:
            goToWeaponAction = GoToAction()
            goToWeaponAction.setDestination(closestWeaponCoords)
            yield goToWeaponAction, "Picking nearby weapon"
        
        # ------------------------------------------
        
        # ROTATE TO SEE MORE

        seeMoreAction = SeeMoreAction()
        yield seeMoreAction, "Rotating to see more"

        # ------------------------------------------
        
        # Go to closest enemy
        attackClosestEnemyAction = AttackClosestEnemyAction()
        yield attackClosestEnemyAction, "Going closer to enemy"

        # ------------------------------------------

        # GO TOWARDS MENHIR

        if menhirPos is not None and distanceToMenhir is not None:
            if distanceToMenhir > 7:
                goCloserToMenhir = True

            if goCloserToMenhir:
                goToAroundAction = GoToAroundAction()
                goToAroundAction.setDestination(menhirPos)
                goToAroundAction.setAllowDangerous(True)
                goToAroundAction.setUseAllMovements(True)
                yield goToAroundAction, "Going closer to menhir"
        
        # ------------------------------------------

        # NOTHING TO DO - JUST SPIN

        spinAction = SpinAction()
        yield spinAction, "No action found, spinning"

        # ==========================================

    @profile
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if DEBUG: print()
        if DEBUG: print("[ARAGORN|BRAIN] Deciding...")

        actionIndexPerformed = 0


        # update state
        
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


        # select actions depending on state

        if self.state == 0:
            actionsFunc = self.prepareActionsOpening
        elif self.state == 1:
            actionsFunc = self.prepareActionsMidGame
        else:
            actionsFunc = self.prepareActionsEndGame

        
        # pick action & perform it

        if DEBUG: print("[ARAGORN|BRAIN] State=", self.state)

        for action, dbg_ac_msg in actionsFunc(knowledge):
            startTime = time.time()
            ret = action.perform(self.memory)
            endTime = time.time()
            self.wholeTime += endTime - startTime
            
            if ret is not None and ret is not characters.Action.DO_NOTHING:
                if DEBUG: print("[ARAGORN|BRAIN]", action.__class__.__name__, dbg_ac_msg)
                self.onDecisionReturning(ret)
                
                return ret
            
            # if ret is None:
            #     if DEBUG: print("[ARAGORN|BRAIN]", "TRIED TO PERFORM ACTION BUT FAILED!", action.__class__.__name__, dbg_ac_msg)
            
            actionIndexPerformed += 1
        
        if DEBUG: print("[ARAGORN|BRAIN] None of actions returned anything, spinning")
        self.onDecisionReturning(characters.Action.TURN_RIGHT)
        
        return characters.Action.TURN_RIGHT
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.memory.reset(arena_description)
        pathfinding.invalidate_PF_cache()
        self.state = 1

        self.__initPersistentActions()
    
    def onDecisionReturning(self, action: characters.Action):
        if action in [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
        ]:
            self.memory.resetIdle()
        
        self.memory.addLastAction(action)
