import random
from typing import Tuple, List

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

from queue import Queue
from collections import defaultdict
import numpy as np
import heapq

mapper = defaultdict(lambda: 1)
mapper["land"] = 0
mapper["menhir"] = 0

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

Point2d = Tuple[int, int]
Direction = Tuple[int, int]


def dist(a: Point2d, b: Point2d) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def heuristic(a, b):
    return np.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)


def astar(map: np.ndarray, start: Point2d, goal: Point2d) -> List[Point2d]:
    neighbors = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    close_set = set()
    came_from = {}
    gscore = {start: 0}
    fscore = {start: heuristic(start, goal)}
    oheap = []
    heapq.heappush(oheap, (fscore[start], start))

    while oheap:
        current = heapq.heappop(oheap)[1]
        if current == goal:
            data = []
            while current in came_from:
                data.append(current)
                current = came_from[current]
            data.reverse()
            return data
        close_set.add(current)
        for i, j in neighbors:
            neighbor = current[0] + i, current[1] + j
            tentative_g_score = gscore[current] + heuristic(current, neighbor)
            if 0 <= neighbor[0] < map.shape[0]:
                if 0 <= neighbor[1] < map.shape[1]:
                    if map[neighbor[0]][neighbor[1]] == 1:
                        continue
                else:
                    continue
            else:
                continue

            if neighbor in close_set and tentative_g_score >= gscore.get(neighbor, 0):
                continue

            if tentative_g_score < gscore.get(neighbor, 0) or neighbor not in [
                i[1] for i in oheap
            ]:
                came_from[neighbor] = current
                gscore[neighbor] = tentative_g_score
                fscore[neighbor] = tentative_g_score + heuristic(neighbor, goal)
                heapq.heappush(oheap, (fscore[neighbor], neighbor))
    return []


class LordIcon(controller.Controller):
    def __init__(self, first_name: str) -> None:
        self.first_name: str = first_name
        self.moves_q = Queue()
        self.do_circle()
        self.map = np.ones((100, 100))
        self.position = (0, 0)
        # turn right = self.facing = self.facing + 1 % len(self.directions)
        self.facing = 0
        self.directions = [
            (0, -1),
            (-1, 0),
            (0, 1),
            (1, 0),
        ]
        self.menhir = None
        self.moves_counter = 20
        self.is_mist_visible = False
        self.never_seen_mist = True
        self.current_direction = None
        self.previous_pos = (0, 0)
        self.previous_move = characters.Action.DO_NOTHING
        self.has_weapon = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LordIcon):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.position = (knowledge.position.x, knowledge.position.y)
        self.furthest_points_x = []
        self.furthest_points_y = []
        max_dist = 0
        closest_weapon = None
        min_dist = 100
        self.mist_tiles_x = []
        self.mist_tiles_y = []

        for coord, tile in knowledge.visible_tiles.items():
            x, y = (
                (coord.x, coord.y)
                if isinstance(coord, coordinates.Coords)
                else (coord[0], coord[1])
            )
            _dist = dist(self.position, (x, y))
            if "mist" in list(map(lambda x: x.type, tile.effects)):
                self.is_mist_visible = True
                if self.is_mist_visible and self.never_seen_mist:
                    self.mist_tiles_x.append(x)
                    self.mist_tiles_y.append(y)

            if _dist < min_dist and tile.loot:
                if tile.loot.name != "knife":
                    min_dist = _dist
                    closest_weapon = (x, y)
            if not self.is_mist_visible and tile.type == "land":
                self.furthest_points_x.append(x)
                self.furthest_points_y.append(y)
            if _dist == 1:
                self.facing = self.directions.index(
                    (x - self.position[0], y - self.position[1])
                )
            self.map[x, y] = mapper[tile.type]
            if tile.character:
                self.map[x, y] = 1
            if tile.type == "menhir":
                self.menhir = (x, y)

        if self.is_mist_visible and self.never_seen_mist:
            self.empty_queue()
            self.never_seen_mist = False
            self.has_weapon = True
            self.mist_tiles_x = np.array(self.mist_tiles_x)
            self.mist_tiles_y = np.array(self.mist_tiles_y)
            x, y = np.indices(self.map.shape)
            x = x[..., np.newaxis] - self.mist_tiles_x
            y = y[..., np.newaxis] - self.mist_tiles_y
            x = np.power(x, 2)
            y = np.power(y, 2)
            dists = x + y
            dists = np.sum(dists, axis=-1)
            dists[self.map != 0] = 0
            max_idx = np.argmax(dists)
            cord_x = max_idx // dists.shape[0]
            cord_y = max_idx % dists.shape[0]
            self.process_moves(astar(self.map, self.position, (cord_x, cord_y)))

        if closest_weapon and not self.has_weapon:
            moves = astar(self.map, self.position, closest_weapon)
            if moves:
                self.has_weapon = True
                self.empty_queue()
                self.process_moves(moves)
            else:
                self.has_weapon = False

        if self.menhir is not None and self.has_weapon and self.is_mist_visible:
            if dist(self.position, self.menhir) < 2 and self.moves_q.empty():
                if self.previous_move == characters.Action.ATTACK:
                    action = random.choice(
                        [
                            characters.Action.TURN_LEFT,
                            characters.Action.TURN_RIGHT,
                            characters.Action.ATTACK,
                        ]
                    )
                    self.previous_move = action
                    return action
                else:
                    self.previous_move = characters.Action.ATTACK
                    return characters.Action.ATTACK

            moves_todo = astar(
                self.map,
                self.position,
                self.menhir,
            )
            if moves_todo:
                self.empty_queue()
                self.process_moves(moves_todo)

        if self.moves_q.empty() and not self.is_mist_visible:
            self.never_seen_mist = False
            self.has_weapon = True
            self.furthest_points_x = np.array(self.furthest_points_x)
            self.furthest_points_y = np.array(self.furthest_points_y)
            x, y = np.indices(self.map.shape)
            x = x[..., np.newaxis] - self.furthest_points_x
            y = y[..., np.newaxis] - self.furthest_points_y
            x = np.power(x, 2)
            y = np.power(y, 2)
            dists = x + y
            dists = np.sum(dists, axis=-1)
            dists[self.map != 0] = 0
            max_idx = np.argmax(dists)
            cord_x = max_idx // dists.shape[0]
            cord_y = max_idx % dists.shape[0]
            moves = astar(self.map, self.position, (cord_x, cord_y))
            if moves:
                self.process_moves(moves)

        if (
            self.previous_pos == self.position
            and self.previous_move == characters.Action.STEP_FORWARD
        ):
            if self.current_direction is not None:
                self.empty_queue()
                self.process_moves(
                    astar(self.map, self.position, self.current_direction)
                )

        self.previous_pos = self.position
        if self.current_direction == self.position:
            self.current_direction = None

        if self.moves_q.empty():
            return random.choices(POSSIBLE_ACTIONS, weights=(1, 1, 3, 1), k=1)[0]
        else:
            action = self.moves_q.get()
            self.previous_move = action
            return action

    def process_moves(self, points: List[Point2d]) -> None:
        if not points:
            return

        self.current_direction = points[-1]

        position = self.position
        for point in points:
            self.move_to(point)
            self.position = point

        self.position = position

    def move_to(self, where: Direction) -> None:
        if self.position == where:
            return

        direction = (where[0] - self.position[0], where[1] - self.position[1])
        self.rotate(direction)
        self.moves_q.put(characters.Action.STEP_FORWARD)
        self.moves_counter -= 1
        if self.moves_counter == 0 and not self.is_mist_visible and self.menhir is None:
            self.do_circle()
            self.moves_counter = 20

    def rotate(self, where: Direction) -> None:
        if self.facing is None:
            return

        if self.direction == where:
            return

        if where not in self.directions:
            return

        where_idx = self.directions.index(where)
        diff = self.facing - where_idx
        if abs(diff) == 2:
            self.moves_q.put(characters.Action.TURN_RIGHT)
            self.moves_q.put(characters.Action.TURN_RIGHT)
        elif diff in [1, -3]:
            self.moves_q.put(characters.Action.TURN_RIGHT)
        elif diff in [-1, 3]:
            self.moves_q.put(characters.Action.TURN_LEFT)

        self.facing = where_idx

    def empty_queue(self):
        self.moves_q.queue.clear()

    def do_circle(self):
        for _ in range(4):
            self.moves_q.put(characters.Action.TURN_RIGHT)

    @property
    def direction(self) -> Direction:
        return self.directions[self.facing]

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.moves_q = Queue()
        self.do_circle()
        self.map = np.ones((100, 100))
        self.position = (0, 0)
        self.facing = 0
        self.menhir = None
        self.moves_counter = 10
        self.is_mist_visible = False
        self.never_seen_mist = True
        self.current_direction = None
        self.previous_pos = (0, 0)
        self.previous_move = characters.Action.DO_NOTHING
        self.has_weapon = False

    @property
    def name(self) -> str:
        return f"RandomController{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.YELLOW
