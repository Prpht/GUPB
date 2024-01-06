from gupb.model import characters, consumables

from gupb.controller.aragorn.actions import *
from gupb.controller.aragorn import pathfinding
from gupb.controller.aragorn import utils
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY

from .strategy import Strategy



class StrategyMidgame(Strategy):
    def prepare_actions(self, brain: 'Brain') -> characters.Action:
        # ------------------------------------------
        
        dangerousTilesDict = brain.memory.map.getDangerousTilesWithDangerSourcePos(brain.memory.tick, 7)

        # ------------------------------------------

        # PREVENT IDLE PENALTY

        if brain.memory.willGetIdlePenalty():
            # TODO: allow to decide action, afterwards, if pos will no change - force spin
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_LEFT)
            yield spinAction, "Spinning to prevent idle penalty"
        
        # ------------------------------------------

        # DEFENDING FROM ATTACKS

        if brain.memory.position in dangerousTilesDict:
            takeToOnesLegsAction = TakeToOnesLegsAction()
            takeToOnesLegsAction.setDangerSourcePos(dangerousTilesDict[brain.memory.position])
            yield takeToOnesLegsAction, "Defending from attack"
        
        # ------------------------------------------

        # PICKING UP POTION

        [closestPotionDistance, closestPotionCoords] = brain.memory.getDistanceToClosestPotion(5)

        if DEBUG2: print("[ARAGORN|BRAIN] closestPotionDistance", closestPotionDistance, "closestPotionCoords", closestPotionCoords)

        if closestPotionDistance is not None and closestPotionDistance < 5:
            goToPotionAction = GoToAction()
            goToPotionAction.setDestination(closestPotionCoords)
            goToPotionAction.setUseAllMovements(True)
            goToPotionAction.setAllowDangerous(True)
            yield goToPotionAction, "Picking nearby potion"

        # ------------------------------------------
        
        # ATTACKING

        oponentInRange = brain.memory.getClosestOponentInRange()

        if DEBUG2: print("[ARAGORN|BRAIN] oponentInRange", oponentInRange, "is on safe tile:", brain.memory.position not in dangerousTilesDict.keys(), "oppo health:", oponentInRange.health if oponentInRange is not None else None, "my health:", brain.memory.health)

        if (
            oponentInRange is not None
            and (
                brain.memory.position not in dangerousTilesDict.keys()
                or (
                    oponentInRange.health <= brain.memory.health
                    and oponentInRange.health <= consumables.POTION_RESTORED_HP
                )
            )
        ):
            attackAction = AttackAction()
            yield attackAction, "Attacking, since got oponent in range"
        
        # ------------------------------------------

        # MIST FORCED MOVEMENT

        [menhirPos, prob] = brain.memory.map.menhirCalculator.approximateMenhirPos(brain.memory.tick)

        if DEBUG2: print("[ARAGORN|BRAIN] menhirPos", menhirPos, "prob", prob)
        
        if menhirPos is not None:
            goCloserToMenhir = False

            if brain.memory.map.mist_radius < 7:
                goCloserToMenhir = True
            
            if not goCloserToMenhir:
                dist = pathfinding.get_path_cost(brain.memory, brain.memory.position, menhirPos, brain.memory.facing, True)

                if dist is None or dist == INFINITY:
                    dist = utils.manhattanDistance(brain.memory.position, menhirPos)
                
                if dist >= brain.memory.map.mist_radius - 5:
                    goCloserToMenhir = True

            if goCloserToMenhir:
                goToAroundAction = GoToAroundAction()
                goToAroundAction.setDestination(menhirPos)
                goToAroundAction.setAllowDangerous(True)
                goToAroundAction.setUseAllMovements(True)
                yield goToAroundAction, "Going closer to menhir"

        # ------------------------------------------
        
        # PICKING UP WEAPON

        [closestWeaponDistance, closestWeaponCoords] = brain.memory.getDistanceToClosestWeapon()

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

        # SNEAKY ATTACK
        sneakyAttackAction = SneakyAttackAction()
        yield sneakyAttackAction, "Sneaky attack"

        # RAGE ATTACK
        rageAttackAction = RageAttackAction()
        yield rageAttackAction, "Rage attack"
        
        # Go to closest enemy
        attackClosestEnemyAction = AttackClosestEnemyAction()
        yield attackClosestEnemyAction, "Going closer to enemy"

        # ------------------------------------------

        # EXPLORE THE MAP

        exploreAction = brain.persistentActions['explore']
        yield exploreAction, "Exploring action"

        # ------------------------------------------

        # NOTHING TO DO - JUST SPIN

        spinAction = SpinAction()
        yield spinAction, "No action found, spinning"

        # ==========================================
