from gupb.model import characters, consumables

from gupb.controller.aragorn.actions import *
from gupb.controller.aragorn.constants import DEBUG, DEBUG2

from .strategy import Strategy



class StrategyOpening(Strategy):
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
        
        # PICKING UP WEAPON

        [closestWeaponDistance, closestWeaponCoords] = brain.memory.getDistanceToClosestWeapon()

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