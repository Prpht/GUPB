import random
from math import atan2
from collections import deque

from gupb.controller.random import POSSIBLE_ACTIONS
from gupb.model import arenas, coordinates
from gupb.model import characters
from gupb.model.arenas import Arena


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class WIETnamczyk:
    def __init__(self):
        self.first_name: str = "Adam"
        self.map = self.parse_map()
        self.arena_description = None

    def parse_map(self):
        arena = Arena.load("fisher_island")
        map_matrix = [[None for i in range(arena.size[0])] for j in range(arena.size[1])]
        for k, v in arena.terrain.items():
            map_matrix[k.x][k.y] = v.description().type
        return map_matrix

    def find_path(self, start_pos, map_matrix, dest_coord):
        X = len(map_matrix)
        Y = len(map_matrix[0])
        visited = [[False for _ in range(X)] for _ in range(Y)]
        parent = {start_pos: None}
        queue = deque([start_pos])

        while len(queue) > 0:
            s = queue.popleft()
            if s == dest_coord:
                path = []
                p = dest_coord
                while parent[p]:
                    path.append(p)
                    p = parent[p]
                return list(reversed(path))

            if not visited[s[0]][s[1]]:
                visited[s[0]][s[1]] = True

                for s_x, s_y in [(-1, 0), (1, 0), (0, 1), (0, -1)]:
                    adj_x = s[0] + s_x
                    adj_y = s[1] + s_y
                    adj = (adj_x, adj_y)
                    if 0 <= adj_x < X and 0 <= adj_y < Y and map_matrix[adj_x][adj_y] == 'land' and not visited[adj_x][adj_y]:
                        queue.append(adj)
                        parent[adj] = s

    def __eq__(self, other: object) -> bool:
        if isinstance(other, WIETnamczyk):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.arena_description = arena_description

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        bot_pos = knowledge.position
        menhir = self.arena_description.menhir_position

        path_to_menhir = self.find_path((bot_pos.x, bot_pos.y), self.map, (menhir.x, menhir.y))


        def dist(tile1: coordinates.Coords, tile2: coordinates.Coords):
            return abs(tile1[0] - tile2[0]) + abs(tile1[1] - tile2[1])

        for tile, description in knowledge.visible_tiles.items():
            distance = dist(bot_pos, tile)
            if distance == 1:
                if description.character:
                    return characters.Action.ATTACK
                if len(path_to_menhir) == 1:
                    return characters.Action.TURN_RIGHT
                next_tile = path_to_menhir[0]

                if next_tile == (tile[0], tile[1]):
                    return characters.Action.STEP_FORWARD

                x1 = next_tile[0] - bot_pos.x
                y1 = next_tile[1] - bot_pos.y
                x2 = tile[0] - bot_pos.x
                y2 = tile[1] - bot_pos.y
                angle = atan2(y2, x2) - atan2(y1, x1)

                if angle > 0:
                    return characters.Action.TURN_LEFT
                else:
                    return characters.Action.TURN_RIGHT

        return random.choice(POSSIBLE_ACTIONS)

    @property
    def name(self) -> str:
        return f'WIETnamczyk{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BLUE


POTENTIAL_CONTROLLERS = [
    WIETnamczyk(),
]