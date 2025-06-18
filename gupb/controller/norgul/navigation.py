from gupb.controller.norgul.memory import Memory
from gupb.controller.norgul.misc import manhattan_dist
from gupb.controller.norgul.config import WEAPON_VALUES

from gupb.model import coordinates

import heapq

from collections import defaultdict
from math import inf
from typing import Tuple


# ---------------
# Navigator class
# ---------------

# A set of algorithms for moving and navigating around given arena
class Navigator:

    def __init__(self, memory: Memory):
        self.memory = memory
        self.arena = memory.arena
    
    # ------------------------
    # Navigator - path finding
    # ------------------------

    # Djikstra algorithm
    # - NOTE: Uses A* extension for speed-up
    def find_path(self, sq_from: coordinates.Coords, sq_to: coordinates.Coords) -> Tuple[coordinates.Coords, bool]:
        '''
            Performs Djikstra algorithm to find the best (defined by connection weights) path from sq_from to sq_to.

            Returns next square on the quickest path from sq_from to sq_to.
            Alternatively, if sq_to is unreachable, returns next square on the quickest path to square that is closest to sq_to (and False as 2nd).
        '''

        if sq_from == sq_to:
            return sq_to

        # Initialize distances to each square
        distances = defaultdict(lambda: inf)
        distances[sq_from] = 0

        # Priority queue representation
        # - First value is a distance to given square
        heap = []
        heapq.heappush(heap, (0, sq_from))

        # Save previously searched squares to reconstruct the best path
        previous = defaultdict(lambda: None)
        closest_alternative = None
        closest_dist = inf

        visited = set()

        while heap:
            dist, sq = heapq.heappop(heap)

            if sq in visited:
                continue

            if sq == sq_to:
                break

            for neighbor in self.arena.adjacent(sq):
                cost = self._connection_cost(sq, neighbor)

                new_dist = dist + cost
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    previous[neighbor] = sq

                    # Add heuristic distance estimation (A*)
                    heapq.heappush(heap, (new_dist + manhattan_dist(neighbor, sq_to), neighbor))
            
            # Update closest alternative path
            # - Manhattan metric
            metric_value = manhattan_dist(sq, sq_to)
            if dist < inf and metric_value < closest_dist:
                closest_alternative = sq
                closest_dist = metric_value
            
            visited.add(sq)

        # Reconstruct the path
        current_sq = sq_to

        can_achieve_to = True

        # No path from sq_from to sq_to
        # - In this case we want to return a path to square which is as close to sq_to as possible
        if previous[current_sq] is None:
            current_sq = closest_alternative
            can_achieve_to = False
            if closest_alternative == sq_from:
                return sq_from, False
   
        while previous[current_sq] != sq_from:
            current_sq = previous[current_sq]
        
        return current_sq, can_achieve_to
    
    # --------------------------------------
    # Navigator - connection cost estimation
    # --------------------------------------
    
    def _connection_cost(self, sq_from: coordinates.Coords, sq_to: coordinates.Coords) -> float:
        ''' Calculates and returns heuristic cost of moving from square sq_from to square sq_to.
        
            In other words, it returns a weight of an edge between sq_from and sq_to or 
            infinity if sq_from and sq_to are not directly connected.
        '''

        if sq_from == sq_to:
            return 0.0
        
        # Squares not connected
        if abs(sq_from[0] - sq_to[0]) + abs(sq_from[1] - sq_to[1]) != 1:
            return inf
        
        # Stone or sea on target square
        if self.arena[sq_to].type in ["sea", "wall"]:
            return inf
        
        # Forest occupied by other (immortal) player
        if self.arena[sq_to].type == "forest" and self.arena[sq_to].character is not None:
            return inf
        
        cost = 1.0

        # Some other character blocking the pass
        # if self.arena[sq_to].character is not None:
        #     cost += 3.0
        
        # Weapons
        if sq_to in self.arena.weapons:
            if self.arena.weapons[sq_to].name in ["scroll", "amulet"]:
                cost += 100.0
            else:
                cost += max(0, WEAPON_VALUES[self.memory.weapon_name] - WEAPON_VALUES[self.arena.weapons[sq_to].name])
        
        # Potions
        if self.arena[sq_to].consumable is not None and self.arena[sq_to].consumable == "potion":
            cost = 0.0

        # Penalize walking through mist or fire
        if self.arena[sq_to].effects and ("mist",) in self.arena[sq_to].effects:
            cost += 10.0
        if self.arena[sq_to].effects and ("fire",) in self.arena[sq_to].effects:
            cost += 50.0

        return cost