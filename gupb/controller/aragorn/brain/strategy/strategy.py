from gupb.model import characters, consumables

from gupb.controller.aragorn.actions import *
from gupb.controller.aragorn import utils
from gupb.controller.aragorn import pathfinding
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY


class Strategy:
    def __init__(self, brain: 'Brain') -> None:
        self._brain = brain
        self._clear_variables()

    def prepare_actions(self) -> characters.Action:
        action = AdvancedExploreAction()
        yield action, "Exploring"
    
    # VARIABLES
    
    def _clear_variables(self):
        self._dangerousTilesDict = None
        self._closestPotionDistance = None
        self._closestPotionCoords = None
        self._menhirPos = None
        self._prob = None
    
    # @property
    # def dangerousTilesDict(self) -> str:
    
    @property
    def dangerousTilesDict(self):
        if self._dangerousTilesDict is None:
            self._dangerousTilesDict = self._brain.memory.map.getDangerousTilesWithDangerSourcePos(self._brain.memory.tick, 3)

        return self._dangerousTilesDict
    
    @property
    def closestPotionDistance(self):
        if self._closestPotionDistance is None:
            self._closestPotionDistance, self._closestPotionCoords = self._brain.memory.getDistanceToClosestPotion(5)
            if DEBUG2: print("[ARAGORN|BRAIN] closestPotionDistance", self._closestPotionDistance, "closestPotionCoords", self._closestPotionCoords)

        return self._closestPotionDistance
    
    @property
    def closestPotionCoords(self):
        if self._closestPotionCoords is None:
            self._closestPotionDistance, self._closestPotionCoords = self._brain.memory.getDistanceToClosestPotion(5)
            if DEBUG2: print("[ARAGORN|BRAIN] closestPotionDistance", self._closestPotionDistance, "closestPotionCoords", self._closestPotionCoords)

        return self._closestPotionCoords
    
    @property
    def menhirPos(self):
        if self._menhirPos is None and self._prob is None:
            self._menhirPos, self._prob = self._brain.memory.map.menhirCalculator.approximateMenhirPos(self._brain.memory.tick)
            if DEBUG2: print("[ARAGORN|BRAIN] menhirPos", self._menhirPos, "prob", self._prob)

        return self._menhirPos
    
    @property
    def prob(self):
        if self._menhirPos is None and self._prob is None:
            self._menhirPos, self._prob = self._brain.memory.map.menhirCalculator.approximateMenhirPos(self._brain.memory.tick)
            if DEBUG2: print("[ARAGORN|BRAIN] menhirPos", self._menhirPos, "prob", self._prob)

        return self._prob
    
        

    # ACTIONS

    def _prevent_idle_penalty(self):
        if self._brain.memory.willGetIdlePenalty():
            spinAction = SpinAction()
            spinAction.setSpin(characters.Action.TURN_LEFT)
            return spinAction, "Spinning to prevent idle penalty"
        
        return None, None
    
    def _defend_from_attacks(self):
        if self._brain.memory.position in self.dangerousTilesDict:
            takeToOnesLegsAction = TakeToOnesLegsAction()
            takeToOnesLegsAction.setDangerSourcePos(self.dangerousTilesDict[self._brain.memory.position])
            return takeToOnesLegsAction, "Defending from attack"
        
        return None, None
    
    def _pick_up_potion(self, distThreshold):
        if self.closestPotionDistance is not None and self.closestPotionDistance < distThreshold:
            goToPotionAction = GoToAction()
            goToPotionAction.setDestination(self.closestPotionCoords)
            goToPotionAction.setUseAllMovements(True)
            goToPotionAction.setAllowDangerous(True)
            return goToPotionAction, "Picking nearby potion"

        return None, None
    
    def _attack_in_range(self, opponentHealthThreshold = consumables.POTION_RESTORED_HP):
        oponentInRange = self._brain.memory.getClosestOponentInRange()

        if DEBUG2: print("[ARAGORN|BRAIN] oponentInRange", oponentInRange, "is on safe tile:", self._brain.memory.position not in self.dangerousTilesDict.keys(), "oppo health:", oponentInRange.health if oponentInRange is not None else None, "my health:", self._brain.memory.health)

        if (
            oponentInRange is not None
            and (
                self._brain.memory.position not in self.dangerousTilesDict.keys()
                or (
                    oponentInRange.health <= self._brain.memory.health
                    and oponentInRange.health <= opponentHealthThreshold
                )
            )
        ):
            attackAction = AttackAction()
            return attackAction, "Attacking, since got oponent in range"
        
        return None, None
    
    def _mist_forced_movement(self):
        if self.menhirPos is not None:
            goCloserToMenhir = False

            if self._brain.memory.map.mist_radius < 7:
                goCloserToMenhir = True
            
            if not goCloserToMenhir:
                dist = pathfinding.get_path_cost(self._brain.memory, self._brain.memory.position, self.menhirPos, self._brain.memory.facing, True)

                if dist is None or dist == INFINITY:
                    dist = utils.manhattanDistance(self._brain.memory.position, self.menhirPos)
                
                if dist >= self._brain.memory.map.mist_radius - 5:
                    goCloserToMenhir = True

            if goCloserToMenhir:
                goToAroundAction = GoToAroundAction()
                goToAroundAction.setDestination(self.menhirPos)
                goToAroundAction.setAllowDangerous(True)
                goToAroundAction.setUseAllMovements(True)
                return goToAroundAction, "Going closer to menhir"
        
        return None, None

    def _conquer_menhir(self):
        if self.menhirPos is not None:
            conquerMenhirAction = ConquerMenhirAction()
            return conquerMenhirAction, "Conquering menhir"

        return None, None
    
    def _pick_up_weapon(self, distThreshold):
        [closestWeaponDistance, closestWeaponCoords] = self._brain.memory.getDistanceToClosestWeapon()
        
        if DEBUG2: print("[ARAGORN|BRAIN] closestWeaponDistance", closestWeaponDistance, "closestWeaponCoords", closestWeaponCoords)

        if closestWeaponCoords is not None and closestWeaponDistance < distThreshold:
            goToWeaponAction = GoToAction()
            goToWeaponAction.setDestination(closestWeaponCoords)
            return goToWeaponAction, "Picking nearby weapon"

        return None, None
    
    def _rotate_to_see_more(self):
        seeMoreAction = SeeMoreAction()
        return seeMoreAction, "Rotating to see more"

    def _attack_approach_sneaky(self):
        sneakyAttackAction = SneakyAttackAction()
        return sneakyAttackAction, "Sneaky attack"
    
    def _attack_approach_rage(self):
        rageAttackAction = RageAttackAction()
        return rageAttackAction, "Rage attack"
    
    def _attack_approach_normal(self):
        attackClosestEnemyAction = AttackClosestEnemyAction()
        return attackClosestEnemyAction, "Going closer to enemy"
    
    def _explore_the_map(self):
        exploreAction = self._brain.persistentActions['explore']
        return exploreAction, "Exploring action"
    
    def _spin(self):
        spinAction = SpinAction()
        return spinAction, "No action found, spinning"

    
