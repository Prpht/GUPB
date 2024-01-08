from abc import abstractmethod

from gupb.model.coordinates import *
from gupb.model import characters

from gupb.controller.aragorn import pathfinding
from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import INFINITY
from .go_to_action import GoToAction
from .attack_action import AttackAction
from .go_to_around_action import GoToAroundAction



class ConquerMenhirAction:
    def perform(self, memory :Memory) -> characters.Action:
        [menhirPos, prob] = memory.map.menhirCalculator.approximateMenhirPos(memory.tick)

        if menhirPos is None:
            # no menhir found
            return None
        
        if memory.position == menhirPos:
            # already on menhir
            return None
        
        isMenhirOccupied = (
            menhirPos in memory.map.terrain
            and memory.map.terrain[menhirPos].character is not None
        )

        if not isMenhirOccupied:
            # menhir is free - go straight to it
            goToAction = GoToAction()
            goToAction.setDestination(menhirPos)
            goToAction.setUseAllMovements(False)
            goToAction.setAllowDangerous(False)
            return goToAction.perform(memory)
        else:
            # menhir is occupied - go around it
            destinationTiles = []
            
            if memory.getCurrentWeaponName() in [
                'amulet'
                'axe',
            ]:
                destinationTiles = [
                    add_coords(menhirPos, Coords(-1, -1)),
                    add_coords(menhirPos, Coords(-1,  1)),
                    add_coords(menhirPos, Coords( 1, -1)),
                    add_coords(menhirPos, Coords( 1,  1)),
                ]
            elif memory.getCurrentWeaponName() in [
                'bow',
                'bow_loaded',
                'bow_unloaded',
            ]:
                destinationTiles = [
                    add_coords(menhirPos, Coords(-4,  0)),
                    add_coords(menhirPos, Coords( 4,  0)),
                    add_coords(menhirPos, Coords( 0, -4)),
                    add_coords(menhirPos, Coords( 0,  4)),

                    add_coords(menhirPos, Coords(-3,  0)),
                    add_coords(menhirPos, Coords( 3,  0)),
                    add_coords(menhirPos, Coords( 0, -3)),
                    add_coords(menhirPos, Coords( 0,  3)),

                    add_coords(menhirPos, Coords(-2,  0)),
                    add_coords(menhirPos, Coords( 2,  0)),
                    add_coords(menhirPos, Coords( 0, -2)),
                    add_coords(menhirPos, Coords( 0,  2)),
                ]
            elif memory.getCurrentWeaponName() in [
                'sword',
            ]:
                destinationTiles = [
                    add_coords(menhirPos, Coords(-3,  0)),
                    add_coords(menhirPos, Coords( 3,  0)),
                    add_coords(menhirPos, Coords( 0, -3)),
                    add_coords(menhirPos, Coords( 0,  3)),

                    add_coords(menhirPos, Coords(-2,  0)),
                    add_coords(menhirPos, Coords( 2,  0)),
                    add_coords(menhirPos, Coords( 0, -2)),
                    add_coords(menhirPos, Coords( 0,  2)),
                ]
            else:
                destinationTiles = [
                    add_coords(menhirPos, Coords(-1,  0)),
                    add_coords(menhirPos, Coords( 1,  0)),
                    add_coords(menhirPos, Coords( 0, -1)),
                    add_coords(menhirPos, Coords( 0,  1)),
                ]
            
            if memory.position not in destinationTiles:
                # go there
                minCost = INFINITY
                minTile = None

                for destinationTile in destinationTiles:
                    path, cost = pathfinding.find_path(
                        memory=memory,
                        start=memory.position,
                        end=destinationTile,
                        facing=memory.facing,
                        useAllMovements=False,
                        avoid_cells=[]
                    )

                    if minCost is None or cost < minCost:
                        minCost = cost
                        minTile = destinationTile
                
                if minTile is None:
                    # no direct path found - just go around menhir
                    goToAroundAction = GoToAroundAction()
                    goToAroundAction.setDestination(menhirPos)
                    goToAroundAction.setAllowDangerous(False)
                    goToAroundAction.setUseAllMovements(False)
                    return goToAroundAction.perform(memory)
                
                goToAction = GoToAction()
                goToAction.setDestination(minTile)
                goToAction.setUseAllMovements(False)
                goToAction.setAllowDangerous(False)
                return goToAction.perform(memory)
            else:
                currentWeapon = memory.getCurrentWeaponClass()

                if currentWeapon is None:
                    return None
                
                rangeCells = currentWeapon.cut_positions(memory.map.terrain, memory.position, memory.facing)

                if menhirPos in rangeCells:
                    # attack menhir
                    attackAction = AttackAction()
                    return attackAction.perform()
                else:
                    # rotate to reach menhir
                    rangeCellsLeft  = currentWeapon.cut_positions(memory.map.terrain, memory.position, memory.facing.turn_left())
                    rangeCellsRight = currentWeapon.cut_positions(memory.map.terrain, memory.position, memory.facing.turn_right())

                    if menhirPos in rangeCellsLeft:
                        return characters.Action.TURN_LEFT
                    elif menhirPos in rangeCellsRight:
                        return characters.Action.TURN_RIGHT
                    else:
                        return characters.Action.TURN_RIGHT
