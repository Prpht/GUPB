from gupb.controller.norgul.memory import Memory

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates


# ------------------
# Motor cortex class
# ------------------

# A class that represents champion's ability to move in a given direction
# - It allows for two ways of moving: quick moves, regarding the champion's sight direction, and slow moves with change of the sight direction
class MotorCortex:

    def __init__(self, memory: Memory):
        self.memory = memory
    
    # ------------------
    # Basic move methods
    # ------------------

    # NOTE: Both of the below methods just return an action to take, they do not apply those actions to champion's state by themselves!

    # Move in a given direction
    def move(self, dir: characters.Facing, quick: bool = False) -> characters.Action | None:
        ''' Returns an appropriate action which is required to move in direction dir 

            If moving is such direction is impossible, it returns None.
        '''
    
        # Calculate target square
        target_sq = self.memory.pos + dir.value

        # Check correctness with respect to arena bounds
        if target_sq not in self.memory.arena:
            return None
        
        # Check player direction vs move direction relation
        if dir == self.memory.dir:
            # If there is another player blocking the target square, we need to eliminate him
            return characters.Action.STEP_FORWARD if self.memory.arena[target_sq].character is None else characters.Action.ATTACK
        if dir == self.memory.dir.turn_right():
            return characters.Action.TURN_RIGHT if not quick else characters.Action.STEP_RIGHT
        elif dir == self.memory.dir.turn_left():
            return characters.Action.TURN_LEFT if not quick else characters.Action.STEP_RIGHT
        else:
            # The move direction is opposite to player's sight direction
            # - NOTE: Here we can either turn left or right in slow version, since both actions are optimal in this case
            return characters.Action.TURN_RIGHT if not quick else characters.Action.STEP_BACKWARD
    
    # Move to a given square
    def move_to(self, target_sq: coordinates.Coords, quick: bool = False) -> characters.Action | None:
        ''' Returns an appropriate action which is required to move to a given square 

            If moving to such square is impossible or target square is already being occupied by Norgul, it returns None.
        '''

        # Let's just calculate the move direction and reuse previous method
        for dir in characters.Facing:
            if target_sq == self.memory.pos + dir.value:
                return self.move(dir=dir, quick=quick)
        
        return None