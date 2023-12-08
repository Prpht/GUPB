from typing import NamedTuple, Optional, List, Tuple

from gupb.model.profiling import profile
from gupb.model.coordinates import *
from gupb.model import characters
from gupb.model import effects

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn import utils
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY, OUR_BOT_NAME, USE_PF_CACHE, OPTIMIZE_PF

cache = {}

def invalidate_PF_cache():
    global cache
    cache = {}

def makeHashable(dict: {Coords: Coords}) -> [Coords]:
    return frozenset(dict.items())

def get_action_to_move_in_path(source: Coords, sourceFacing: characters.Facing, destination: Coords, useAllMovements :bool = False) -> characters.Action:
    direction = sub_coords(destination, source)

    if useAllMovements:
        if direction == sourceFacing.value:
            return characters.Action.STEP_FORWARD
        elif direction == sourceFacing.turn_left().value:
            return characters.Action.STEP_LEFT
        elif direction == sourceFacing.turn_right().value:
            return characters.Action.STEP_RIGHT
        else:
            return characters.Action.STEP_BACKWARD
    else:
        if direction == sourceFacing.value:
            return characters.Action.STEP_FORWARD
        elif direction == sourceFacing.turn_left().value:
            return characters.Action.TURN_LEFT
        elif direction == sourceFacing.turn_right().value:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_RIGHT
    
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
    # TODO: remove facing param - it's not used
    global cache

    if USE_PF_CACHE:
        cacheKey = (start, end, useAllMovements)
        
        if cacheKey in cache:
            return cache[cacheKey]
    
    if OPTIMIZE_PF:
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

    def get_h_cost(memory: Memory, h_start: Coords, h_end: Coords) -> int:
        distance: int = abs(h_end.y - h_start.y) + abs(h_end.x - h_start.x)
        return distance + tile_cost(memory, h_start)

    def tile_cost(memory: Memory, tileCoords: Coords) -> int:
        mistCost = 0
        
        if tileCoords in memory.map.terrain and effects.Mist in memory.map.terrain[tileCoords].effects:
            mistCost = 200
        
        dangerousTileCost = 0

        if tileCoords in memory.map.getDangerousTilesWithDangerSourcePos(memory.tick):
            # if dist = 1, cost += 200
            # if dist = 2, cost += 180
            # ...
            # if dist = 10, cost += 20
            # if dist = 11, cost += 0
            # if dist = 12, cost += 0
            dangerousTileCost = 20 * max( (10 - utils.coordinatesDistance(memory.position, tileCoords) + 1), 0 )

        return mistCost + dangerousTileCost

    a_coords = NamedTuple('a_coords', [('coords', Coords),
                                        ('g_cost', int),
                                        ('h_cost', int),
                                        ('parent', Optional[Coords])])
    
    open_coords: [a_coords] = []
    closed_coords: {Coords: a_coords} = {}
    open_coords.append(a_coords(start, 0, get_h_cost(memory, start, end), None))
    
    while len(open_coords) > 0:
        open_coords = list(sorted(open_coords, key=lambda x: (x.g_cost, x.h_cost), reverse=False))
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
            
            # if DEBUG2:
            #     print('----------')
            #     for y in range(memory.map.size[1]):
            #         for x in range(memory.map.size[0]):
            #             tmp_coords = Coords(x, y)
            #             cost = None

            #             if cost is None:
            #                 if tmp_coords in closed_coords:
            #                     cost = closed_coords[tmp_coords].g_cost # + closed_coords[tmp_coords].h_cost

            #             if cost is None:
            #                 for oc in open_coords:
            #                     if oc.coords == tmp_coords:
            #                         cost = oc.g_cost # + oc.h_cost
                                    

            #             if tmp_coords == start:
            #                 cost = 'S' + str(cost)

            #             if tmp_coords == end:
            #                 cost = 'E' + str(cost)
                        
            #             print(
            #                 str(cost if cost is not None else '-').ljust(4),
            #                 end=' '
            #             )
            #         print()
            #     print('----------')
            
            return trace, int(current.h_cost + current.g_cost)

        neighbors: [Coords] = [add_coords(current.coords, (Coords(0, 1))),
                                add_coords(current.coords, (Coords(0, -1))),
                                add_coords(current.coords, (Coords(1, 0))),
                                add_coords(current.coords, (Coords(-1, 0)))]

        for neighbor in neighbors:
            if not neighbor in memory.map.terrain:
                continue
            
            if OPTIMIZE_PF:
                if neighbor.x < considerFrom.x or neighbor.x > considerTo.x or neighbor.y < considerFrom.y or neighbor.y > considerTo.y:
                    continue

            if (
                neighbor in memory.map.terrain.keys()
                and memory.map.terrain[neighbor].terrain_passable()
                # and (memory.map.terrain[neighbor].character is None or memory.map.terrain[neighbor].character.controller_name == OUR_BOT_NAME) # check if enemy is not in the way
                and neighbor not in closed_coords.keys()
            ):
                neighbor_g_cost = 1 + current.g_cost + tile_cost(memory, neighbor)
                neighbor_h_cost = get_h_cost(memory, neighbor, end)

                for coords in open_coords:
                    if coords.coords == neighbor:
                        open_coords.remove(coords)

                open_coords.append(a_coords(neighbor,
                                            neighbor_g_cost,
                                            neighbor_h_cost,
                                            current.coords))
    
    trace: Optional[List[Coords]] = None
    
    if USE_PF_CACHE:
        cache[cacheKey] = (trace, INFINITY)
    
    return trace, INFINITY

def get_path_cost(memory: Memory, start: Coords, end: Coords, facing: characters.Facing, useAllMovements :bool = False) -> int:
    return find_path(memory, start, end, facing, useAllMovements)[1]
