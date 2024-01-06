from gupb.model.coordinates import *
from gupb.model import characters, weapons
from gupb.model.profiling import profile

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.memory import Map
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY
from gupb.controller.aragorn import pathfinding
from gupb.controller.aragorn import utils

from .action import Action
from .attack_closest_enemy_action import AttackClosestEnemyAction
from .go_to_action import GoToAction



class SneakyAttackAction(AttackClosestEnemyAction):
    def approachEnemy(self, memory: Memory, closestEnemyCoords: Coords, closestEnemyDistance: int) -> Action:
        # CLOSEST ENEMY IS TOO FAR
        # just approach him
        if (
            # closestEnemyDistance > 3
            closestEnemyCoords in memory.map.terrain
            and memory.map.terrain[closestEnemyCoords].character is not None
            and (not hasattr(memory.map.terrain[closestEnemyCoords], 'tick') or memory.map.terrain[closestEnemyCoords].tick >= memory.tick - 2)
        ):
            if DEBUG2: print("[ARAGORN|SNEAKY_ATTACK_ENEMY] Closest enemy is too far, going closer")

            closestEnemyDescription = memory.map.terrain[closestEnemyCoords].character
            enemyFacing = closestEnemyDescription.facing
            enemyWeapon = Map.weaponDescriptionConverter(closestEnemyDescription.weapon)

            # if enemy holding amulet, dont sneak,
            # since they will see us anyway
            if enemyWeapon != weapons.Amulet:
                tileBehindEnemy = closestEnemyCoords + enemyFacing.turn_right().turn_right().value

                opponentsVisibleTiles = memory.map.visible_coords(
                    enemyFacing,
                    closestEnemyCoords,
                    enemyWeapon
                )
                opponentsVisibleTiles = list(opponentsVisibleTiles)

                goToSneakyAction = GoToAction()
                goToSneakyAction.setDestination(tileBehindEnemy)
                goToSneakyAction.setUseAllMovements(True)
                goToSneakyAction.setAvoidCells(opponentsVisibleTiles)
                retSneaky = goToSneakyAction.perform(memory)
                costSneaky = goToSneakyAction.get_last_path_cost()

                goToNormalAction = GoToAction()
                goToNormalAction.setDestination(closestEnemyCoords)
                goToNormalAction.setUseAllMovements(True)
                retNormal = goToNormalAction.perform(memory)
                costNormal = goToNormalAction.get_last_path_cost()
                
                if costSneaky < costNormal + 4:
                    return retSneaky
                elif closestEnemyDistance > 3:
                    return retNormal

        return super().approachEnemy(memory, closestEnemyCoords, closestEnemyDistance)
