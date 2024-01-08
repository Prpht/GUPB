import random
from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.tiles import TileDescription
from gupb.model.effects import EffectDescription
from gupb.controller.alpha_gupb.pathfinder import pathfinder

POSSIBLE_ACTIONS = [
    characters.Action.TURN_RIGHT,
    characters.Action.TURN_LEFT,
    characters.Action.STEP_FORWARD
]

def go_right_slow(facing):
    if(facing == characters.Facing.RIGHT):
        return characters.Action.STEP_FORWARD
    if(facing == characters.Facing.LEFT):
        return characters.Action.TURN_LEFT
    if(facing == characters.Facing.UP):
        return characters.Action.TURN_RIGHT
    if(facing == characters.Facing.DOWN):
        return characters.Action.TURN_LEFT
    
def go_left_slow(facing):
    if(facing == characters.Facing.RIGHT):
        return characters.Action.TURN_LEFT
    if(facing == characters.Facing.LEFT):
        return characters.Action.STEP_FORWARD
    if(facing == characters.Facing.UP):
        return characters.Action.TURN_LEFT
    if(facing == characters.Facing.DOWN):
        return characters.Action.TURN_RIGHT
    
def go_up_slow(facing):
    if(facing == characters.Facing.UP):
        return characters.Action.STEP_FORWARD
    if(facing == characters.Facing.LEFT):
        return characters.Action.TURN_RIGHT
    if(facing == characters.Facing.RIGHT):
        return characters.Action.TURN_LEFT
    if(facing == characters.Facing.DOWN):
        return characters.Action.TURN_LEFT   
    
def go_down_slow(facing):
    if(facing == characters.Facing.RIGHT):
        return characters.Action.TURN_RIGHT
    if(facing == characters.Facing.LEFT):
        return characters.Action.TURN_LEFT
    if(facing == characters.Facing.UP):
        return characters.Action.TURN_LEFT
    if(facing == characters.Facing.DOWN):
        return characters.Action.STEP_FORWARD   



def go_right(facing):
    if facing == characters.Facing.RIGHT:
        return characters.Action.STEP_FORWARD
    elif facing == characters.Facing.UP:
        return characters.Action.STEP_RIGHT
    elif facing == characters.Facing.DOWN:
        return characters.Action.STEP_LEFT
    elif facing ==characters.Facing.LEFT:
        return characters.Action.STEP_BACKWARD
    
def go_left(facing):
    if facing == characters.Facing.LEFT:
        return characters.Action.STEP_FORWARD
    elif facing == characters.Facing.UP:
        return characters.Action.STEP_LEFT
    elif facing == characters.Facing.DOWN:
        return characters.Action.STEP_RIGHT
    elif facing == characters.Facing.RIGHT:
        return characters.Action.STEP_BACKWARD

def go_up(facing):
    if facing == characters.Facing.UP:
        return characters.Action.STEP_FORWARD
    elif facing == characters.Facing.RIGHT:
        return characters.Action.STEP_LEFT
    elif facing == characters.Facing.LEFT:
        return characters.Action.STEP_RIGHT
    elif facing == characters.Facing.DOWN:
        return characters.Action.STEP_BACKWARD

def go_down(facing):
    if facing == characters.Facing.DOWN:
        return characters.Action.STEP_FORWARD
    elif facing == characters.Facing.LEFT:
        return characters.Action.STEP_LEFT
    elif facing == characters.Facing.RIGHT:
        return characters.Action.STEP_RIGHT
    elif facing == characters.Facing.UP:
        return characters.Action.STEP_BACKWARD
    