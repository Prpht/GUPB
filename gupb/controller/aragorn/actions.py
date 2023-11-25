from abc import abstractmethod
from random import choice
from typing import NamedTuple, Optional, List, Tuple

from gupb.model.coordinates import *
from gupb.model import characters

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, INFINITY



class Action:
    @abstractmethod
    def perform(self, memory :Memory) -> characters.Action:
        raise NotImplementedError

class SpinAction(Action):
    def __init__(self) -> None:
        super().__init__()
        self.spin = characters.Action.TURN_RIGHT
    
    def perform(self, memory :Memory) -> characters.Action:
        return self.spin
    
    def setSpin(self, spin: characters.Action) -> None:
        if spin not in [
            characters.Action.TURN_RIGHT,
            characters.Action.TURN_LEFT
        ]:
            return
        
        self.spin = spin

class RandomAction(Action):
    def perform(self, memory: Memory) -> characters.Action:
        available_actions = [characters.Action.STEP_FORWARD, characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
        random_action = choice(available_actions)
        return random_action

class AttackAction(Action):
    def perform(self, memory: Memory) -> Action:
        return characters.Action.ATTACK

class GoToAction(Action):
    def __init__(self) -> None:
        super().__init__()
        self.destination: Coords = None
        self.dstFacing: characters.Facing = None

    def setDestination(self, destination: Coords) -> None:
        if isinstance(destination, Coords):
            self.destination = destination
        else:
            if DEBUG:
                print("Trying to set destination to non Coords object (" + str(destination) + " of type " + str(type(destination)) + ")")

    def setDestinationFacing(self, dstFacing: characters.Facing) -> None:
        if isinstance(dstFacing, characters.Facing):
            self.dstFacing = dstFacing
        else:
            if DEBUG:
                print("Trying to set destination facing to non Facing object (" + str(dstFacing) + " of type " + str(type(dstFacing)) + ")")

    def perform(self, memory :Memory) -> characters.Action:        
        if not self.destination:
            return None
        
        current_position = memory.position
        
        if current_position == self.destination:
            if self.dstFacing is not None and memory.facing != self.dstFacing:
                # TODO: not always turning right is optimal
                return characters.Action.TURN_RIGHT
            return None
        
        [path, cost] = self.find_path(memory=memory, start=current_position, end=self.destination, facing = memory.facing)

        if path is None or len(path) <= 1:
            return None

        nextCoord = path[1]
        
        return self.get_action_to_move_in_path(memory, nextCoord)

    def get_facing(self, f_coords: Coords) -> characters.Facing:
        if f_coords == Coords(0, 1):
            return characters.Facing.DOWN
        elif f_coords == Coords(0, -1):
            return characters.Facing.UP
        elif f_coords == Coords(1, 0):
            return characters.Facing.LEFT
        elif f_coords == Coords(-1, 0):
            return characters.Facing.RIGHT

    def get_action_to_move_in_path(self, memory: Memory, destination: Coords) -> characters.Action:
        direction = sub_coords(destination, memory.position)

        if direction == memory.facing.value:
            return characters.Action.STEP_FORWARD
        elif direction == memory.facing.turn_left().value:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT
    
    def find_path(self, memory: Memory, start: Coords, end: Coords, facing: characters.Facing) -> (Optional[List[Coords]], int):
        def get_h_cost(memory: Memory, h_start: Coords, h_end: Coords, h_facing: characters.Facing) -> int:
            distance: int = abs(h_end.y - h_start.y) + abs(h_end.x - h_start.x)
            direction: Coords = Coords(1 if h_end.x - h_start.x > 0 else -1 if h_end.x - h_start.x < 0 else 0,
                                       1 if h_end.y - h_start.y > 0 else -1 if h_end.y - h_start.y < 0 else 0)
            
            turnDiffX = abs(h_facing.value.x - direction.x)
            turnDiffY = abs(h_facing.value.y - direction.y)

            if turnDiffX == 1 and turnDiffY == 1:
                turns = 1
            elif turnDiffX == 2 or turnDiffY == 2:
                turns = 2
            else:
                turns = 0
            
            mistCost = 0
            
            if memory.map.terrain[h_end].__class__.__name__.lower() == 'menhir':
                mistCost = 40
            
            dangerousTileCost = 0

            if h_end in memory.map.getDangerousTiles():
                dangerousTileCost = 10

            return (turns if turns <= 2 else 2) + distance + mistCost + dangerousTileCost

        a_coords = NamedTuple('a_coords', [('coords', Coords),
                                           ('g_cost', int),
                                           ('h_cost', int),
                                           ('parent', Optional[Coords]),
                                           ('facing', characters.Facing)])
        
        open_coords: [a_coords] = []
        closed_coords: {Coords: a_coords} = {}
        open_coords.append(a_coords(start, 0, get_h_cost(memory, start, end, facing), None, facing))
        
        while len(open_coords) > 0:
            open_coords = list(sorted(open_coords, key=lambda x: (x.g_cost + x.h_cost, x.h_cost), reverse=False))
            current: a_coords = open_coords.pop(0)
            closed_coords[current.coords] = current
            
            if current.coords == end:
                trace: Optional[List[Coords]] = [current.coords]
                current_parent: Optional[a_coords] = current

                while current_parent.parent is not None:
                    current_parent = closed_coords[current_parent.parent]
                    trace.insert(0, current_parent.coords)

                return trace, int(current.h_cost + current.g_cost)

            neighbors: [Coords] = [add_coords(current.coords, (Coords(0, 1))),
                                   add_coords(current.coords, (Coords(0, -1))),
                                   add_coords(current.coords, (Coords(1, 0))),
                                   add_coords(current.coords, (Coords(-1, 0)))]

            for neighbor in neighbors:
                if not neighbor in memory.map.terrain:
                    continue

                if (
                        neighbor in memory.map.terrain.keys()\
                        and memory.map.terrain[neighbor].terrain_passable()\
                        and neighbor not in closed_coords.keys()
                ):
                    neighbor_direction: Coords = Coords(neighbor.x - current.coords.x, neighbor.y - current.coords.y)
                    neighbor_g_cost = (1 if neighbor_direction == current.facing.value else
                                       3 if add_coords(neighbor_direction, current.facing.value) == Coords(0, 0) else 2) \
                                      + current.g_cost
                    
                    neighbor_h_cost = get_h_cost(memory, neighbor, end, self.get_facing(neighbor_direction))

                    for coords in open_coords:
                        if coords.coords == neighbor:
                            open_coords.remove(coords)

                    open_coords.append(a_coords(neighbor,
                                                neighbor_g_cost,
                                                neighbor_h_cost,
                                                current.coords,
                                                self.get_facing(neighbor_direction)))
        
        trace: Optional[List[Coords]] = None
        return trace, INFINITY

class GoToAroundAction(GoToAction):
    def perform(self, memory: Memory) -> Action:
        if memory.position == self.destination:    
            return None

        actionToPerform = super().perform(memory)
        
        limit = 25
        destinationsGenerator = self.__aroundTileGenerator(self.destination)

        while actionToPerform is None and limit > 0:
            limit -= 1
            
            try:
                self.setDestination(destinationsGenerator.__next__())
            except StopIteration:
                pass

            actionToPerform = super().perform(memory)
        
        return actionToPerform

    def __aroundTileGenerator(self, aroundDestination :Coords):
        if not isinstance(aroundDestination, Coords):
            return None
        
        for r in range(7):
            for x in range(-r, r + 1):
                for y in range(-r, r + 1):
                    if (x - aroundDestination.x) ** 2 + (y - aroundDestination.y) ** 2 == r ** 2:
                        yield Coords(x, y)
