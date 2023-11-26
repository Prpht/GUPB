from typing import NamedTuple, Optional, List, Tuple

from gupb.model.profiling import profile
from gupb.model.coordinates import *
from gupb.model import characters
from gupb.model import effects

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, INFINITY, OUR_BOT_NAME, USE_PF_CACHE

cache = {}

def invalidate_PF_cache():
    global cache
    cache = {}

def makeHashable(dict: {Coords: Coords}) -> [Coords]:
    return frozenset(dict.items())

def get_action_to_move_in_path(source: Coords, sourceFacing: characters.Facing, destination: Coords, useAllMovements :bool = False) -> characters.Action:
    direction = sub_coords(destination, source)

    if direction == sourceFacing.value:
        return characters.Action.STEP_FORWARD
    elif direction == sourceFacing.turn_left().value:
        return characters.Action.STEP_LEFT
    elif direction == sourceFacing.turn_right().value:
        return characters.Action.STEP_RIGHT
    else:
        if not useAllMovements:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.STEP_BACKWARD
    
def get_facing(f_coords: Coords) -> characters.Facing:
    if f_coords == Coords(0, 1):
        return characters.Facing.DOWN
    elif f_coords == Coords(0, -1):
        return characters.Facing.UP
    elif f_coords == Coords(1, 0):
        return characters.Facing.LEFT
    elif f_coords == Coords(-1, 0):
        return characters.Facing.RIGHT

@profile
def find_path(memory: Memory, start: Coords, end: Coords, facing: characters.Facing, useAllMovements :bool = False) -> (Optional[List[Coords]], int):
    global cache

    if USE_PF_CACHE:
        cacheKey = (start, end, facing, useAllMovements)
        
        if cacheKey in cache:
            return cache[cacheKey]
    
    considerFrom = Coords(
        min(start.x, end.x) - 5,
        min(start.y, end.y) - 5,
    )
    considerTo = Coords(
        max(start.x, end.x) + 5,
        max(start.y, end.y) + 5,
    )

    if considerTo.x - considerFrom.x < 10:
        considerTo.x -= 10
        considerFrom.x += 10
    
    if considerTo.y - considerFrom.y < 10:
        considerTo.y -= 10
        considerFrom.y += 10

    def get_h_cost(memory: Memory, h_start: Coords, h_end: Coords, h_facing: characters.Facing, useAllMovements :bool = False) -> int:
        distance: int = abs(h_end.y - h_start.y) + abs(h_end.x - h_start.x)
        direction: Coords = Coords(1 if h_end.x - h_start.x > 0 else -1 if h_end.x - h_start.x < 0 else 0,
                                    1 if h_end.y - h_start.y > 0 else -1 if h_end.y - h_start.y < 0 else 0)
        
        if useAllMovements:
            turns = 0
        else:
            turnDiffX = abs(h_facing.value.x - direction.x)
            turnDiffY = abs(h_facing.value.y - direction.y)

            if turnDiffX == 1 and turnDiffY == 1:
                turns = 1
            elif turnDiffX == 2 or turnDiffY == 2:
                turns = 2
            else:
                turns = 0
        
        mistCost = 0
        
        if h_end in memory.map.terrain and effects.Mist in memory.map.terrain[h_end].effects:
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
    open_coords.append(a_coords(start, 0, get_h_cost(memory, start, end, facing, useAllMovements), None, facing))
    
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

            if USE_PF_CACHE:
                cache[cacheKey] = (trace, int(current.h_cost + current.g_cost))
            
            return trace, int(current.h_cost + current.g_cost)

        neighbors: [Coords] = [add_coords(current.coords, (Coords(0, 1))),
                                add_coords(current.coords, (Coords(0, -1))),
                                add_coords(current.coords, (Coords(1, 0))),
                                add_coords(current.coords, (Coords(-1, 0)))]

        for neighbor in neighbors:
            if not neighbor in memory.map.terrain:
                continue

            if neighbor.x < considerFrom.x or neighbor.x > considerTo.x or neighbor.y < considerFrom.y or neighbor.y > considerTo.y:
                continue

            if (
                    neighbor in memory.map.terrain.keys()
                    and memory.map.terrain[neighbor].terrain_passable()
                    and (memory.map.terrain[neighbor].character is None or memory.map.terrain[neighbor].character.controller_name == OUR_BOT_NAME) # check if enemy is not in the way
                    and neighbor not in closed_coords.keys()
            ):
                neighbor_direction: Coords = Coords(neighbor.x - current.coords.x, neighbor.y - current.coords.y)
                neighbor_g_cost = (1 if neighbor_direction == current.facing.value else
                                    3 if add_coords(neighbor_direction, current.facing.value) == Coords(0, 0) else 2) \
                                    + current.g_cost
                
                neighbor_h_cost = get_h_cost(memory, neighbor, end, get_facing(neighbor_direction), useAllMovements)

                for coords in open_coords:
                    if coords.coords == neighbor:
                        open_coords.remove(coords)

                open_coords.append(a_coords(neighbor,
                                            neighbor_g_cost,
                                            neighbor_h_cost,
                                            current.coords,
                                            get_facing(neighbor_direction)))
    
    trace: Optional[List[Coords]] = None
    
    if USE_PF_CACHE:
        cache[cacheKey] = (trace, INFINITY)
    
    return trace, INFINITY

def get_path_cost(memory: Memory, start: Coords, end: Coords, facing: characters.Facing) -> int:
    return find_path(memory, start, end, facing)[1]
