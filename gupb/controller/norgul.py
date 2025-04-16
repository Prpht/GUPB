import heapq
import numpy as np
import random
import traceback
from itertools import product
from collections import defaultdict
from math import inf, sqrt

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles


class NorgulController(controller.Controller):
    Norgulium = "Norgulium"

    def __init__(norgul, first_name: str = "Norgul"):
        norgul.first_name: str = first_name

        # Global arena state
        # - Used to build connection graph and find path to given square
        norgul.arena_width = 0
        norgul.arena_height = 0
        norgul.arena : dict[coordinates.Coords, tiles.TileDescription] = {}
        norgul.saw_mist = False
        norgul.obelisk_pos = None  # menhir
        norgul.current_pos = None
        norgul.current_dir = None
        norgul.current_weapon = "knife"

        norgul.time_count = 0

        # Hyperparameters
        norgul.radius = 4
        norgul.mist_vec_weight = 50
        norgul.enemy_vec_weight = 5


    def __eq__(norgul, other: object) -> bool:
        if isinstance(other, NorgulController):
            return norgul.first_name == other.first_name
        return False


    def __hash__(norgul) -> int:
        return hash(norgul.first_name)


    def decide(norgul, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # norgul.time_count += 1
        # if norgul.time_count % 10 == 0:
        #     norgul._forget_other_characters()

        # Step 1
        # - Update arena state based on obtained knowledge)
        norgul.current_pos = knowledge.position
        norgul.current_dir = knowledge.visible_tiles[norgul.current_pos].character.facing
        norgul.current_weapon = knowledge.visible_tiles[norgul.current_pos].character.weapon.name
        action = None

        for coord, tile_info in knowledge.visible_tiles.items():
            norgul.arena[coord] = tile_info
            if tile_info.type == "menhir":
                norgul.obelisk_pos = coord
            if norgul.arena[coord].effects and ("mist",) in norgul.arena[coord].effects:
                norgul.saw_mist = True

        # Step 2
        # - Locate target square (either escaping mist / enemies or not) !!!
        target = norgul.pick_target()

        # Step 3
        # - Move towards target square
        action = norgul.move_to_target(target, fast=False)

        # print(action)

        # Step 4
        # - If target square (or set of squares) is already reached, rotate and gain more knowledge
        return action if action is not None else characters.Action.TURN_RIGHT


    def praise(norgul, score: int) -> None:
        pass


    def reset(norgul, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        arena_path = "resources/arenas/" + arena_description.name + ".gupb"
        norgul._load_arena_state(arena_path)
        norgul.obelisk_pos = None
        norgul.current_pos = None
        norgul.current_dir = None
        norgul.saw_mist = False
        norgul.current_weapon = "knife"

    def pick_target(norgul):
        if not norgul.saw_mist:
            target_sq = norgul._pick_forest()
            if target_sq is not None:
                return target_sq

        # Calculate current important zone around our character
        character_zone = [norgul.current_pos + diff for diff in product(range(-norgul.radius, norgul.radius + 1),
                                                                        range(-norgul.radius, norgul.radius + 1))]
        character_zone = [sq for sq in character_zone if 0 <= sq[0] < norgul.arena_height and 0 <= sq[1] < norgul.arena_width]
        
        # Target vector
        target_vec = np.array([0.0, 0.0])

        # Mist center calculation
        mist_mean = np.array([0.0, 0.0])
        mist_count = 0

        for sq in character_zone:
            if norgul.arena[sq].effects and ("mist",) in norgul.arena[sq].effects:
                mist_mean = mist_mean + sq
                mist_count += 1
            if norgul.arena[sq].character is not None and sq != norgul.current_pos:
                vec = np.array(norgul.current_pos) - sq
                target_vec = target_vec + (vec * norgul.enemy_vec_weight)
        
        # Calculate mist center and add mist vector
        if mist_count > 0:
            mist_mean = mist_mean / mist_count
            vec = np.array(norgul.current_pos) - mist_mean
            target_vec = target_vec + (vec * norgul.mist_vec_weight)
        
        
        if target_vec[0] == 0 and target_vec[1] == 0:
            return norgul.current_pos
        
        # Normalize target vector
        target_vec = target_vec * (1 / sqrt(target_vec[0] ** 2 + target_vec[1] ** 2))

        target_sq = norgul.current_pos
        for i in range(1, 10):
            some_sq = np.array(norgul.current_pos) + target_vec * i
            some_sq = coordinates.Coords(int(some_sq[0]), int(some_sq[1]))
            if not (0 <= some_sq[0] < norgul.arena_width) or not (0 <= some_sq[1] < norgul.arena_height):
                continue
            if abs(some_sq[0] - norgul.current_pos[0]) <= norgul.radius and abs(some_sq[1] - norgul.current_pos[1]) <= norgul.radius:
                target_sq = some_sq
        
        return target_sq


    def _pick_forest(norgul) -> coordinates.Coords:
        if norgul.arena[norgul.current_pos].type == "forest":
            return norgul.current_pos

        character_zone = [norgul.current_pos + diff for diff in product(range(-norgul.radius, norgul.radius + 1),
                                                                        range(-norgul.radius, norgul.radius + 1))]
        character_zone = [sq for sq in character_zone if 0 <= sq[0] < norgul.arena_height and 0 <= sq[1] < norgul.arena_width]

        min_distance = inf
        best_sq = None
        for sq in character_zone:
            distance = norgul._manhattan_distance(norgul.current_pos, sq)
            if norgul.arena[sq].type == "forest" and norgul.arena[sq].character is None and distance < min_distance:
                min_distance = distance
                best_sq = sq

        return best_sq


    def move_to_target(norgul, target, fast=False):
        """If Fast -> do not waste moves to turn"""

        next_sq = norgul._find_path(norgul.current_pos, target)

        if norgul.current_pos != next_sq:
            if next_sq != norgul.current_pos + norgul.current_dir.value:
                if next_sq == norgul.current_pos + norgul.current_dir.turn_right().value:
                    return characters.Action.TURN_RIGHT if not fast else characters.Action.STEP_RIGHT
                elif next_sq == norgul.current_pos + norgul.current_dir.turn_left().value:
                    return characters.Action.TURN_LEFT if not fast else characters.Action.STEP_LEFT
                else:
                    return characters.Action.TURN_LEFT if not fast else characters.Action.STEP_BACKWARD
            elif norgul.arena[next_sq].character is not None:
                return characters.Action.ATTACK
            else:
                return characters.Action.STEP_FORWARD

        
        elif norgul.arena[norgul.current_pos + norgul.current_dir.value].character is not None:
            if norgul.arena[norgul.current_pos + norgul.current_dir.value].type == "forest":
                return None
            return characters.Action.ATTACK


    def _load_arena_state(norgul, arena_path: str) -> None:
        ''' Loads and saves given arena state'''

        with open(arena_path, "r", encoding="utf-8") as file:
            for i, line in enumerate(file):
                for j, tile in enumerate(line):
                    if str.isspace(tile):
                        continue

                    coords = coordinates.Coords(j, i)
                    tile_type = arenas.TILE_ENCODING[tile] if not str.isalpha(tile) else tiles.Land
                    tile_name = tile_type.__name__.lower()
                    weapon_name = arenas.WEAPON_ENCODING[tile].__name__.lower() if str.isalpha(tile) else None

                    norgul.arena[coords] = tiles.TileDescription(tile_name, weapon_name, None, None, [])  # TODO sieci sie, nie ma byc [] ?

                    norgul.arena_width = j + 1
                
                norgul.arena_height = i + 1
    
    def _forget_other_characters(norgul) -> None:
        ''' Clears all the information about other characters from arena state map'''

        for cord in norgul.arena:
            norgul.arena[cord].character = None
    

    def _find_path(norgul, sq_from: coordinates.Coords, sq_to: coordinates.Coords) -> coordinates.Coords:
        '''
            Performs Djikstra algorithm to find the best (defined by connection weights) path from sq_from to sq_to.

            Returns next square on the quickest path from sq_from to sq_to.
            Alternatively, if sq_to is unreachable, returns next square on the quickest path to square that is closest to sq_to.
        '''

        if sq_from == sq_to:
            return sq_to

        # Initialize distances to each square
        distances = {coord: inf for coord in norgul.arena}
        distances[sq_from] = 0

        # Priority queue representation
        # - First value is a distance to given square
        heap = []
        heapq.heappush(heap, (0, sq_from))

        # Save previously searched squares to reconstruct the best path
        previous = {coord: None for coord in norgul.arena}
        closest_alternative = None
        closest_dist = inf

        visited = set()

        while heap:
            dist, sq = heapq.heappop(heap)

            if sq in visited:
                continue

            if sq == sq_to:
                break

            for neighbor in norgul._connections(sq):
                cost = norgul._connection_cost(sq, neighbor)

                new_dist = dist + cost
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    previous[neighbor] = sq
                    heapq.heappush(heap, (new_dist, neighbor))
            
            # Update closest alternative path
            # - Manhattan metric
            metric_value = norgul._manhattan_distance(sq, sq_to)
            if dist < inf and metric_value < closest_dist:
                closest_alternative = sq
                closest_dist = metric_value
            
            visited.add(sq)

        # Reconstruct the path
        current_sq = sq_to

        # No path from sq_from to sq_to
        # - In this case we want to return a path to square which is as close to sq_to as possible
        if previous[current_sq] is None:
            current_sq = closest_alternative
            if closest_alternative == sq_from:
                return sq_from
   
        while previous[current_sq] != sq_from:
            current_sq = previous[current_sq]
        
        return current_sq
    

    def _connection_cost(norgul, sq_from: coordinates.Coords, sq_to: coordinates.Coords) -> float:
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
        if norgul.arena[sq_to].type in ["sea", "wall"]:
            return inf
        
        cost = 100.0

        # Some other character blocking the pass
        if norgul.arena[sq_to].character is not None:
            cost += 5.0

        # Potions
        if norgul.arena[sq_to].consumable is not None and norgul.arena[sq_to].consumable == "potion":
            cost -= 49
        
        # Weapons
        if norgul.arena[sq_to].loot is not None and norgul.arena[sq_to].loot in ["scroll", "amulet"]:
            cost += 1000

        # Penalize walking through mist or fire
        if norgul.arena[sq_to].effects and ("mist",) in norgul.arena[sq_to].effects:
            cost += 25
        if norgul.arena[sq_to].effects and ("fire",) in norgul.arena[sq_to].effects:
            cost += 50

        return max(cost, 1)
    

    def _connections(norgul, sq_from: coordinates.Coords) -> list[coordinates.Coords]:
        ''' Returns all adjacent squares (which can be accessed in one move from sq_from)'''

        squares = [sq_from + dir.value for dir in characters.Facing]

        return [sq for sq in squares if 0 <= sq[0] < norgul.arena_height and 0 <= sq[1] < norgul.arena_width]


    def _manhattan_distance(norgul, coord1, coord2) -> int:
        return abs(coord1[0] - coord2[0]) + abs(coord1[1] - coord2[1])


    @property
    def name(norgul) -> str:
        return f'{norgul.first_name}'

    @property
    def preferred_tabard(norgul) -> characters.Tabard:
        return characters.Tabard.NORGUL


POTENTIAL_CONTROLLERS = [
    NorgulController("Norgul"),
]