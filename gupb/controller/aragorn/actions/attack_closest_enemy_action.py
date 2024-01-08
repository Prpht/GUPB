from gupb.model.coordinates import *
from gupb.model import characters
from gupb.model import weapons
from gupb.model.profiling import profile

from .action import Action
from .go_to_action import GoToAction
from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY
from gupb.controller.aragorn import pathfinding
from gupb.controller.aragorn import utils



class AttackClosestEnemyAction(Action):
    OUTDATED_DATA_TICKS = 16

    def getClosestEnemy(self, memory: Memory):
        closestEnemy = None
        closestEnemyDistance = INFINITY

        if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] Searching for closest enemy")

        for coords in memory.map.terrain:
            if (
                # tile has character
                memory.map.terrain[coords].character is not None
                # ignore if data is outdated
                and (not hasattr(memory.map.terrain[coords], 'tick') or memory.map.terrain[coords].tick >= memory.tick - self.OUTDATED_DATA_TICKS)
                # ignore ourselfs
                # and memory.map.terrain[coords].character.controller_name != OUR_BOT_NAME
                # ignore our position
                and memory.position != coords
                # ignore enemies with greater health
                # and memory.map.terrain[coords].character.health <= memory.health
                # ignore enemies with health greater than reward of killing (potion restore)
                # and memory.map.terrain[coords].character.health <= consumables.POTION_RESTORED_HP
            ):
                distance = utils.manhattanDistance(memory.position, coords)
                
                if distance < closestEnemyDistance:
                    closestEnemy = coords
                    closestEnemyDistance = distance
        
        for enemyName, possiblePositions in memory.map.enemiesPositionsApproximation.enemies.items():
            if len(possiblePositions) > 0 and len(possiblePositions) <= 5:
                coords = possiblePositions[0]

                distance = utils.manhattanDistance(memory.position, coords)

                if distance < closestEnemyDistance:
                    closestEnemy = coords
                    closestEnemyDistance = distance
        
        if closestEnemy is None:
            if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] No closest enemy found")
            return None, INFINITY
        
        if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] Closest enemy found at", closestEnemy, "with distance", closestEnemyDistance)

        return closestEnemy, closestEnemyDistance
        
    def approachEnemy(self, memory: Memory, closestEnemy: Coords, closestEnemyDistance: int) -> Action:
        # CLOSEST ENEMY IS TOO FAR
        # just approach him
        if closestEnemyDistance > 3:
            if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] Closest enemy is too far, going closer")
            goToAttackAction = GoToAction()
            goToAttackAction.setDestination(closestEnemy)
            goToAttackAction.setUseAllMovements(True)
            ret = goToAttackAction.perform(memory)
            if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] Closest enemy is too far, going closer, result:", ret)
            return ret

        # IF CLOSEST ENEMY IS NEARBY
        # GET CLOSEST FIELD YOU CAN ATTACK FROM
        # BY CALCULATING DETAILED PATHS COSTS
        if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] Closest enemy is nearby, calculating detailed paths costs")
        currentWeapon :weapons.Weapon = memory.getCurrentWeaponClass()

        if currentWeapon is None:
            return None
        
        positionsToAttackFrom = {}
        minNormalDistance = INFINITY

        for facing in [
            characters.Facing.UP,
            characters.Facing.DOWN,
            characters.Facing.LEFT,
            characters.Facing.RIGHT,
        ]:
            for pos in currentWeapon.cut_positions(memory.map.terrain, closestEnemy, facing.turn_left().turn_left()):
                tmpDistance = utils.manhattanDistance(memory.position, pos)
                
                if tmpDistance < minNormalDistance:
                    minNormalDistance = tmpDistance
                
                if tmpDistance > minNormalDistance + 1:
                    # do not add positions that are too far
                    continue

                positionsToAttackFrom[(pos, facing)] = INFINITY
        
        for (pos, facing) in positionsToAttackFrom:
            tmpDistance = utils.manhattanDistance(memory.position, pos)
            
            if tmpDistance > minNormalDistance + 1:
                # do not add positions that are too far
                # - leave them as INFINITY
                continue

            positionsToAttackFrom[(pos, facing)] = pathfinding.get_path_cost(memory, memory.position, pos, facing)
        
        minCost = INFINITY
        minCostPos = None
        minCostFacing = None

        for (pos, facing) in positionsToAttackFrom:
            if positionsToAttackFrom[(pos, facing)] < minCost:
                minCost = positionsToAttackFrom[(pos, facing)]
                minCostPos = pos
                minCostFacing = facing
        
        if minCostPos is None:
            return None
        
        # GO TO CLOSEST FIELD YOU CAN ATTACK FROM

        goToAttackAction = GoToAction()
        goToAttackAction.setDestination(minCostPos)
        goToAttackAction.setDestinationFacing(minCostFacing)
        goToAttackAction.setUseAllMovements(True)
        return goToAttackAction.perform(memory)

    @profile
    def perform(self, memory: Memory) -> Action:
        closestEnemy, closestEnemyDistance = self.getClosestEnemy(memory)
        
        if closestEnemy is None:
            return None
        
        return self.approachEnemy(memory, closestEnemy, closestEnemyDistance)
