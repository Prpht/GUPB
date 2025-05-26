import random
import traceback
from collections import defaultdict
from heapq import heappush, heappop

from gupb import controller
from gupb.model import arenas, characters, coordinates

def manhattan_distance(a, b):
    ax, ay = (a.x, a.y) if hasattr(a, 'x') else a
    bx, by = (b.x, b.y) if hasattr(b, 'x') else b
    return abs(ax - bx) + abs(ay - by)

def a_star_escape(start, terrain, is_safe, goal_hint, max_depth=10):

    frontier = []
    heappush(frontier, (0, start, []))
    visited = set()

    while frontier:
        cost, current, path = heappop(frontier)
        if current in visited:
            continue
        visited.add(current)

        if is_safe(current):
            return path

        if len(path) >= max_depth:
            continue

        for direction in characters.Facing:
            neighbor = current + direction.value
            tile = terrain.get(neighbor)
            if neighbor in visited or tile is None or not tile.passable:
                continue
            # priority: path length so far + heuristic to goal_hint
            priority = len(path) + manhattan_distance(neighbor, goal_hint)
            heappush(frontier, (priority, neighbor, path + [direction]))

    return []


class Keramzytowy_mocarz(controller.Controller):
    """
    Keramzytowy Mocarz Bot: heuristic exploration/defense with A* panic escape & adjustable aggression.
    """

    def __init__(self, first_name: str, delta: float = 0.0):
        self.first_name = first_name
        self.delta = delta              
        self.visited = defaultdict(int)
        self.terrain = None             

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Keramzytowy_mocarz) and self.first_name == other.first_name

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.visited.clear()
        self.terrain = arenas.Arena.load(arena_description.name).terrain
    def praise(self, score: int) -> None:
        # Normalizuj wynik względem maksymalnego (np. 250)
        normalized = score / 250

        # Dostosuj agresję
        if normalized > 0.75:
            self.delta = min(self.delta + 0.05, 1.0)
        elif normalized < 0.5:
            self.delta = max(self.delta - 0.05, 0.0)

        if normalized < 0.3:
            self.gamma = min(getattr(self, 'gamma', 2.0) + 0.2, 3.5)
        elif normalized > 0.8:
            self.gamma = max(getattr(self, 'gamma', 2.0) - 0.2, 1.0)

        print(f"[{self.name}] PRAISE: score={score}, delta={self.delta:.2f}, gamma={getattr(self, 'gamma', '?'):.2f}")


    @property
    def name(self) -> str:
        return f'Keramzytowy Mocarz {self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KERAMZYTOWY_MOCARZ

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            my_pos = knowledge.position
            visible_tiles = knowledge.visible_tiles
            my_tile = visible_tiles.get(my_pos)
            if not my_tile or not my_tile.character:
                return characters.Action.TURN_RIGHT

            facing = my_tile.character.facing
            self.visited[my_pos] += 1

            
            mist_positions = [
                coordinates.Coords(*coords) if isinstance(coords, tuple) else coords
                for coords, tile in visible_tiles.items()
                if any(e.type == 'mist' for e in tile.effects)
            ]
            enemy_positions = [
                coords for coords, tile in visible_tiles.items()
                if tile.character and tile.character.controller_name != self.name
            ]

            # PANIC MODE: A* escape if mist is within 2 steps
            min_mist_dist = min((manhattan_distance(my_pos, mist) for mist in mist_positions), default=10)
            if min_mist_dist <= 3 and self.terrain:
                
                def is_safe(pos):
                    tile = self.terrain.get(pos)
                    return tile is not None and tile.passable and not any(
                        e.type == 'mist' for e in getattr(tile, 'effects', ())
                    )

                goal_hint = coordinates.Coords(40, 40)
                path = a_star_escape(my_pos, self.terrain, is_safe, goal_hint, max_depth=10)
                if path:
                    dir0 = path[0]
                    print(f"[{self.name}] Panic A* escape: {dir0.name}")
                    if dir0 == facing:
                        next_pos = my_pos + facing.value
                        self.visited[next_pos] += 1
                        return characters.Action.STEP_FORWARD
                    elif dir0 == facing.turn_left():
                        return characters.Action.TURN_LEFT
                    elif dir0 == facing.turn_right():
                        return characters.Action.TURN_RIGHT
                    elif dir0 == facing.turn_left().turn_left():
                        return characters.Action.TURN_LEFT
                    elif dir0 == facing.turn_right().turn_right():
                        return characters.Action.TURN_RIGHT

            
            alpha, beta, gamma = 3.5, 0.7, 2
            delta_grad, epsilon = 2.5, 0.2

            # compute average mist vector
            if mist_positions:
                dx = sum(mist.x - my_pos.x for mist in mist_positions) / len(mist_positions)
                dy = sum(mist.y - my_pos.y for mist in mist_positions) / len(mist_positions)
                mist_vec = coordinates.Coords(int(round(dx)), int(round(dy)))
            else:
                mist_vec = coordinates.Coords(0, 0)
            center = coordinates.Coords(40, 40)

            move_candidates = []
            for direction in characters.Facing:
                new_pos = my_pos + direction.value
                tile = visible_tiles.get(new_pos)
                if not tile or tile.character or tile.type not in ['land', 'forest', 'menhir']:
                    continue
                if any(e.type == 'mist' for e in tile.effects):
                    continue

                dist_mist = min((manhattan_distance(new_pos, mist) for mist in mist_positions), default=10)
                dist_enemy = min((manhattan_distance(new_pos, enemy) for enemy in enemy_positions), default=10)
                visits = self.visited[new_pos]

                
                grad_bonus = 0
                if mist_vec.x or mist_vec.y:
                    desired = coordinates.Coords(-mist_vec.x, -mist_vec.y)
                    dot = direction.value.x * desired.x + direction.value.y * desired.y
                    grad_bonus = dot

                dist_center = manhattan_distance(new_pos, center)

                score = (
                    dist_mist * alpha
                    - visits * beta
                    + dist_enemy * gamma
                    + grad_bonus * delta_grad
                    - dist_center * epsilon
                )
                move_candidates.append((score, direction))

            if move_candidates:
                move_candidates.sort(key=lambda x: x[0], reverse=True)
                best_score, best_dir = move_candidates[0]
                
                if best_score < 5:
                    for d in characters.Facing:
                        adj = my_pos + d.value
                        t = visible_tiles.get(adj)
                        if t and t.character and t.character.controller_name != self.name:
                            print(f"[{self.name}] Emergency adjacent attack")
                            return characters.Action.ATTACK

                if best_dir == facing:
                    next_pos = my_pos + facing.value
                    self.visited[next_pos] += 1
                    return characters.Action.STEP_FORWARD
                elif best_dir == facing.turn_left():
                    return characters.Action.TURN_LEFT
                elif best_dir == facing.turn_right():
                    return characters.Action.TURN_RIGHT
                elif best_dir == facing.turn_left().turn_left():
                    return characters.Action.TURN_LEFT
                elif best_dir == facing.turn_right().turn_right():
                    return characters.Action.TURN_RIGHT

            
            if random.random() < self.delta:
                for d in characters.Facing:
                    adj = my_pos + d.value
                    t = visible_tiles.get(adj)
                    if t and t.character and t.character.controller_name != self.name:
                        print(f"[{self.name}] Aggressive attack (Δ={self.delta})")
                        return characters.Action.ATTACK

           
            return random.choice([characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT])

        except Exception:
            print(f"[{self.name}] EXCEPTION IN DECIDE:")
            traceback.print_exc()
            return characters.Action.TURN_RIGHT
POTENTIAL_CONTROLLERS = [
    Keramzytowy_mocarz("Hudoka"),
]