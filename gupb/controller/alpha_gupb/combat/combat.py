import random
from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.tiles import TileDescription
from gupb.model.effects import EffectDescription
from gupb.controller.alpha_gupb.pathfinder import pathfinder
import copy
from typing import NamedTuple, Optional, List


def attackable_tiles(weapon, position):
    if weapon == 'bow_loaded':
        attackable_tiles_down = []
        attackable_tiles_left = []
        attackable_tiles_right = []
        attackable_tiles_up = []
        for y in range(position[1] + 1, 50):
            attackable_tiles_down.append((position[0], y))

        for y in range(position[1] - 1, -50, -1):
            attackable_tiles_up.append((position[0], y))

        for x in range(position[0] - 1, -50, -1):
            attackable_tiles_left.append((x, position[1]))

        for x in range(position[0] + 1, 50):
            attackable_tiles_right.append((x, position[1]))
        
    elif weapon == 'sword':
        attackable_tiles_right = [(position[0] + 1, position[1]),
                                  (position[0] + 2, position[1]),
                                  (position[0] + 3, position[1])]
        
        attackable_tiles_left = [(position[0] - 1, position[1]),
                                 (position[0] - 2, position[1]),
                                 (position[0] - 3, position[1])]
        
        attackable_tiles_up = [(position[0], position[1] - 1),
                               (position[0], position[1] - 2),
                               (position[0], position[1] - 3)]

        attackable_tiles_down = [(position[0], position[1] + 1),
                                 (position[0], position[1] + 2),
                                 (position[0], position[1] + 3)]

    elif weapon == 'axe':
        attackable_tiles_left = [(position[0] - 1, position[1] - 1),
                                 (position[0] - 1, position[1]),
                                 (position[0] - 1, position[1] + 1)]
        
        attackable_tiles_right = [(position[0] + 1, position[1] - 1),
                                  (position[0] + 1, position[1]),
                                  (position[0] + 1, position[1] + 1)]
        
        attackable_tiles_up = [(position[0] - 1, position[1] - 1),
                               (position[0], position[1] - 1),
                               (position[0] + 1, position[1] - 1)]
        
        attackable_tiles_down = [(position[0] - 1, position[1] + 1),
                                 (position[0], position[1] + 1),
                                 (position[0] + 1, position[1] + 1)]
        
    elif weapon == 'amulet':
        attackable_tiles_left = attackable_tiles_down = attackable_tiles_right = attackable_tiles_up = [(position[0] + 1, position[1] + 1),
                                                                                                        (position[0] - 1, position[1] + 1),
                                                                                                        (position[0] + 1, position[1] - 1),
                                                                                                        (position[0] - 1, position[1] - 1),
                                                                                                        (position[0] + 2, position[1] + 2),
                                                                                                        (position[0] - 2, position[1] + 2),
                                                                                                        (position[0] + 2, position[1] - 2),
                                                                                                        (position[0] - 2, position[1] - 2)]
    elif weapon == 'knife':
        attackable_tiles_left = [(position[0] - 1, position[1])]
        attackable_tiles_right = [(position[0] + 1, position[1])]
        attackable_tiles_up = [(position[0], position[1] - 1)]
        attackable_tiles_down = [(position[0], position[1] + 1)]


    else:
        return [], [], [], []
    
    return attackable_tiles_left,attackable_tiles_right, attackable_tiles_up, attackable_tiles_down
    



def attack_enemy(facing, direction):
    if(direction == "left"):
        if(facing == characters.Facing.LEFT):
            return characters.Action.ATTACK
        elif(facing == characters.Facing.UP):
            return characters.Action.TURN_LEFT
        elif(facing == characters.Facing.DOWN):
            return characters.Action.TURN_RIGHT
        
    if(direction == "right"):
        if(facing == characters.Facing.RIGHT):
            return characters.Action.ATTACK
        elif(facing == characters.Facing.UP):
            return characters.Action.TURN_RIGHT
        elif(facing == characters.Facing.DOWN):
            return characters.Action.TURN_LEFT
            
    if(direction == "up"):          
        if(facing == characters.Facing.UP):
            return characters.Action.ATTACK
        elif(facing == characters.Facing.LEFT):
            return characters.Action.TURN_RIGHT
        elif(facing == characters.Facing.RIGHT):
            return characters.Action.TURN_LEFT
        
    if(direction == "down"):
        if(facing == characters.Facing.DOWN):
            return characters.Action.ATTACK
        elif(facing == characters.Facing.RIGHT):
            return characters.Action.TURN_RIGHT
        elif(facing == characters.Facing.LEFT):
            return characters.Action.TURN_LEFT
        
    return characters.Action.TURN_LEFT


    
def can_attack_check(enemies, attackable_tiles):
    attackable_tiles_left,attackable_tiles_right, attackable_tiles_up, attackable_tiles_down = attackable_tiles
    if (len(attackable_tiles_down)+len(attackable_tiles_left)+len(attackable_tiles_right)+len(attackable_tiles_up)==0):
        return False
    if not enemies:
        return False
    for enemy in enemies: 
        if enemy in attackable_tiles_left:
            return "left"
        if enemy in attackable_tiles_right:
            return "right"
        if enemy in attackable_tiles_up:
            return "up"
        if enemy in attackable_tiles_down:
            return "down"
    return False
