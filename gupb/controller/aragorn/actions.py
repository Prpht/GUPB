from abc import abstractmethod

from gupb.model import arenas, coordinates, weapons
from gupb.model.coordinates import *
from typing import NamedTuple, Optional, List, Tuple


from gupb.model import characters
from random import choice
from gupb.controller.aragorn.memory import Memory
INFINITY: int = 99999999999

from gupb.model.tiles import TileDescription



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

class GoToAction(Action):
    def __init__(self) -> None:
        super().__init__()
        self.destination: Coords = None
        self.dstFacing: characters.Facing = None
        self.dangerous_tiles: List[Coords] = []
        self.misty_tiles: List[Coords] = []
        self.future_dangerous_tiles: List[Coords] = []
        # self.tiles: {Coords: TileDescription} = {}
        self.facing = characters.Facing.DOWN
        self.good_weapon_in_sight = None
        self.consumable_coords = None


    def setDestination(self, destination: Coords) -> None:
        self.destination = destination

    def setDestinationFacing(self, dstFacing: characters.Facing) -> None:
        self.dstFacing = dstFacing

    def perform(self, memory :Memory) -> characters.Action:
        self.facing = memory.facing
        
        if not self.destination:
            return None
        
        current_position = memory.position
        
        if current_position == self.destination:
            if self.dstFacing is not None and memory.facing != self.dstFacing:
                # TODO: not always turning right is optimal
                return characters.Action.TURN_RIGHT
            return None
        
        # for tile in memory.visible_tiles:
        #     if memory.visible_tiles[tile].effects is not None and memory.visible_tiles[tile].effects != []:
        #         if Coords(tile[0], tile[1]) not in self.misty_tiles:
        #             self.misty_tiles.append(Coords(tile[0], tile[1]))
        #         if Coords(tile[0], tile[1]) not in self.dangerous_tiles:
        #             self.dangerous_tiles.append(Coords(tile[0], tile[1]))

        #     if memory.visible_tiles[tile].consumable is not None:
        #         self.consumable_coords = Coords(tile[0], tile[1])

        #     if memory.visible_tiles[tile].loot is not None:
        #         if memory.visible_tiles[tile].loot.name in ('axe', 'sword'):
        #             self.good_weapon_in_sight = Coords(tile[0], tile[1])

        #     self.tiles[Coords(tile[0], tile[1])] = memory.visible_tiles[tile]
        
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

        if direction == self.facing.value:
            return characters.Action.STEP_FORWARD
        elif direction == self.facing.turn_left().value:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT
    
    def find_path(self, memory: Memory, start: Coords, end: Coords, facing: characters.Facing, dangerous=False, risky=False) -> (Optional[List[Coords]], int):
        def get_h_cost(h_start: Coords, h_end: Coords, h_facing: characters.Facing) -> int:
            distance: int = abs(h_end.y - h_start.y) + abs(h_end.x - h_start.x)
            direction: Coords = Coords(1 if h_end.x - h_start.x > 0 else -1 if h_end.x - h_start.x < 0 else 0,
                                       1 if h_end.y - h_start.y > 0 else -1 if h_end.y - h_start.y < 0 else 0)
            turns = abs(h_facing.value.x - direction.x) + abs(h_facing.value.y - direction.y)
            return (turns if turns <= 2 else 2) + distance

        a_coords = NamedTuple('a_coords', [('coords', Coords),
                                           ('g_cost', int),
                                           ('h_cost', int),
                                           ('parent', Optional[Coords]),
                                           ('facing', characters.Facing)])
        
        open_coords: [a_coords] = []
        closed_coords: {Coords: a_coords} = {}
        open_coords.append(a_coords(start, 0, get_h_cost(start, end, facing), None, facing))

        risky_path = None if risky else self.find_path(memory, start, end, facing, dangerous, True)

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

                if not risky:
                    if int(current.h_cost + current.g_cost) > risky_path[1] + 10:
                        return risky_path

                return trace, int(current.h_cost + current.g_cost)

            neighbors: [Coords] = [add_coords(current.coords, (Coords(0, 1))),
                                   add_coords(current.coords, (Coords(0, -1))),
                                   add_coords(current.coords, (Coords(1, 0))),
                                   add_coords(current.coords, (Coords(-1, 0)))]

            for neighbor in neighbors:
                if not neighbor in memory.map.terrain:
                    continue

                if neighbor in memory.map.terrain.keys()\
                        and memory.map.terrain[neighbor].terrain_passable()\
                        and neighbor not in closed_coords.keys()\
                        and (dangerous or neighbor not in self.dangerous_tiles)\
                        and (risky or neighbor not in self.future_dangerous_tiles):
                    neighbor_direction: Coords = Coords(neighbor.x - current.coords.x, neighbor.y - current.coords.y)
                    neighbor_g_cost = (1 if neighbor_direction == current.facing.value else
                                       3 if add_coords(neighbor_direction, current.facing.value) == Coords(0, 0) else 2) \
                                      + current.g_cost
                    
                    neighbor_h_cost = get_h_cost(neighbor, end, self.get_facing(neighbor_direction))

                    for coords in open_coords:
                        if coords.coords == neighbor:
                            open_coords.remove(coords)

                    open_coords.append(a_coords(neighbor,
                                                neighbor_g_cost,
                                                neighbor_h_cost,
                                                current.coords,
                                                self.get_facing(neighbor_direction)))
        if not risky:
            return risky_path
        if not dangerous:
            return self.find_path(memory, start, end, facing, True, True)
        trace: Optional[List[Coords]] = None
        return trace, INFINITY


class RandomAction(Action):
    def perform(self, memory: Memory) -> characters.Action:
        available_actions = [characters.Action.STEP_FORWARD, characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
        random_action = choice(available_actions)
        return random_action

class AttackAction(Action):
    def perform(self, memory: Memory) -> Action:
        return characters.Action.ATTACK
