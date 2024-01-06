from gupb.model import characters, consumables

from gupb.controller.aragorn.actions import *
from gupb.controller.aragorn import utils
from gupb.controller.aragorn import pathfinding
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY

from .strategy import Strategy



class StrategyEndgame(Strategy):
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
        distanceToMenhir = None

        if DEBUG2: print("[ARAGORN|BRAIN] menhirPos", menhirPos, "prob", prob)
        
        if menhirPos is not None:
            goCloserToMenhir = False
            
            if not goCloserToMenhir:
                distanceToMenhir = pathfinding.get_path_cost(brain.memory, brain.memory.position, menhirPos, brain.memory.facing, True)

                if distanceToMenhir is None or distanceToMenhir == INFINITY:
                    distanceToMenhir = utils.manhattanDistance(brain.memory.position, menhirPos)

                if distanceToMenhir >= brain.memory.map.mist_radius - 1:
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