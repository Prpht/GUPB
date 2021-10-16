import numpy as np
from queue import PriorityQueue

from gupb.model import arenas
from gupb.model import characters
from gupb.model.coordinates import Coords


def r(x):
    return tuple(reversed(x))


COORDS_ZERO = Coords(0, 0)
SAFE_POS = [
    Coords(9, 34),
    Coords(12, 15),
    Coords(30, 5),
    Coords(39, 10),
    Coords(30, 42),
    Coords(39, 26)
]


# starting from start_pos and facing 'facing', compute map where each entry is distance from the start
def dijkstra(arr, start_pos, facing):
    y_max = len(arr)
    x_max = len(arr[0])

    facing = facing.value
    ans = np.full((y_max, x_max), 1 << 14, dtype=np.int16)

    ans[r(start_pos)] = 0
    q = PriorityQueue()
    q.put((0, start_pos, facing))
    while not q.empty():
        val, pos, face = q.get()

        if val != ans[r(pos)]:
            continue

        for delta in characters.Facing:
            delta = delta.value
            new_pos = pos + delta
            try:
                if arr[new_pos.y][new_pos.x] in ['#', '=']:
                    continue
            except IndexError:
                continue

            new_val = val
            if delta == face:
                new_val += 1
            elif delta + face == COORDS_ZERO:
                new_val += 3
            else:
                new_val += 2

            if new_val < ans[r(new_pos)]:
                ans[r(new_pos)] = new_val
                q.put((new_val, new_pos, delta))

    return ans


class FunnyController:
    START_RUNNING_FROM_MIST = 1100
    RUN_DELAY = 25
    MENHIR_NOT_FOUND_LOCATION = Coords(25, 25)

    def __init__(self):
        with open("resources/arenas/fisher_island.gupb", "r") as f:
            self.arena = f.read().split("\n")[:-1]

        self.reset(None)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FunnyController):
            return True
        return False

    def __hash__(self) -> int:
        return 57

    FACING_LIST = [e for e in characters.Facing]
    FACING_DELTAS = {
        characters.Facing.UP: [(0, -3), (0, -2), (0, -1), (-1, -1), (1, -1)],
        characters.Facing.DOWN: [(0, 3), (0, 2), (0, 1), (-1, 1), (1, 1)],
        characters.Facing.LEFT: [(-3, 0), (-2, 0), (-1, 0), (-1, -1), (-1, 1)],
        characters.Facing.RIGHT: [(3, 0), (2, 0), (1, 0), (1, -1), (1, 1)]
    }

    # for each weapon on arena, calculate it`s dijkstra map (see 'dijkstra' above)
    def _fill_to_weapon_map(self):
        y_max = len(self.arena)
        x_max = len(self.arena[0])

        #weapon_types = {'A': 0, 'B': 0, 'S': 0, 'M': 0}
        weapon_types = {'A': 0, 'B': 0, 'S': 0}
        weapons = []

        for y in range(y_max):
            for x in range(x_max):
                tile = self.arena[y][x]
                if tile in weapon_types.keys():
                    weapons.append((tile + str(weapon_types[tile]), Coords(x, y)))
                    weapon_types[tile] += 1

        for weapon, coords in weapons:
            self.to_weapon_map[weapon] = dijkstra(self.arena, coords, characters.Facing.UP)

    # given character pos and map where each entry is distance from destination,
    # compute action to get from pos to destination
    def compute_actions(self, map, pos, facing, delay=0):
        facing = facing.value
        actions = []
        while map[r(pos)] != 0:
            curr_val = map[r(pos)]
            nexxt = None
            for delta in [facing] + [e.value for e in FunnyController.FACING_LIST if e.value != facing]:
                new_pos = pos + delta
                try:
                    new_val = map[r(new_pos)]
                    if new_val < curr_val:
                        curr_val = new_val
                        nexxt = new_pos
                except IndexError:
                    continue

            direction = nexxt - pos
            if direction == facing:
                pass
            elif direction + facing == COORDS_ZERO:
                actions.extend([characters.Action.TURN_RIGHT, characters.Action.TURN_RIGHT])
            elif facing[0] * direction[1] - facing[1] * direction[0] < 0:
                actions.append(characters.Action.TURN_LEFT)
            else:
                actions.append(characters.Action.TURN_RIGHT)

            actions.append(characters.Action.STEP_FORWARD)
            if delay != 0:
                actions.extend([characters.Action.ATTACK] * delay)

            pos = nexxt
            facing = direction

        self.action_iter = 0
        self.actions = actions

    # calculate facing direction based on observation
    @staticmethod
    def _get_facing(knowledge: characters.ChampionKnowledge):
        all_less_x = all_more_x = all_less_y = True
        pos = knowledge.position
        for coords in knowledge.visible_tiles.keys():
            if coords[0] > pos.x:
                all_less_x = False
            elif coords[0] < pos.x:
                all_more_x = False

            if coords[1] > pos.y:
                all_less_y = False

        if all_less_x:
            return characters.Facing.LEFT
        elif all_more_x:
            return characters.Facing.RIGHT
        elif all_less_y:
            return characters.Facing.UP
        else:
            return characters.Facing.DOWN

    def _reset_surrounding_walls(self):
        self.surrounding_walls = {
            characters.Facing.UP: 0,
            characters.Facing.DOWN: 0,
            characters.Facing.LEFT: 0,
            characters.Facing.RIGHT: 0
        }

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        y_max = len(self.arena)
        x_max = len(self.arena[0])

        self.empty_tiles = set()
        for y in range(y_max):
            for x in range(x_max):
                if self.arena[y][x] == '.':
                    self.empty_tiles.add((x, y))

        self.ep_it = 0
        self.facing = None
        self.strategy_iter = 0  # 0-find weapon, 1-find menhir, 2-hide, 4-go to mehnir
        self._reset_surrounding_walls()

        self.to_weapon_map = {}
        self._fill_to_weapon_map()

        self.menhir_pos = None

        self.actions = None
        self.action_iter = 0

    def _find_weapon(self, pos):
        weapon_distances = {key: map[r(pos)] for key, map in self.to_weapon_map.items()}
        closest_weapon = min(weapon_distances, key=weapon_distances.get)

        self.compute_actions(self.to_weapon_map[closest_weapon],
                             pos, self.facing)

    def _find_menhir(self, pos):
        look_next = next(iter(self.empty_tiles))
        to_next_map = dijkstra(self.arena, Coords(*look_next), self.facing)

        self.compute_actions(to_next_map, pos, self.facing)

    def _hold_pos(self, knowledge: characters.ChampionKnowledge):
        opposing_character = False
        pos = knowledge.position
        for delta_x, delta_y in FunnyController.FACING_DELTAS[self.facing]:
            try:
                if knowledge.visible_tiles[(pos[0] + delta_x, pos[1] + delta_y)].character is not None:
                    opposing_character = True
            except KeyError:
                pass

        if opposing_character:
            return characters.Action.ATTACK

        self.surrounding_walls[self.facing] = \
            -1 if self.arena[pos.y + self.facing.value.y][pos.x + self.facing.value.x] != '.' else 1

        turn = characters.Action.TURN_RIGHT
        if (self.facing == characters.Facing.UP and self.surrounding_walls[characters.Facing.LEFT] != -1) or \
                (self.facing == characters.Facing.LEFT and self.surrounding_walls[characters.Facing.DOWN] != -1) or\
                (self.facing == characters.Facing.DOWN and self.surrounding_walls[characters.Facing.RIGHT] != -1) or \
                (self.facing == characters.Facing.RIGHT and self.surrounding_walls[characters.Facing.UP] != -1):
            turn = characters.Action.TURN_LEFT

        return turn

    def _hide(self, pos):
        if self.menhir_pos is None:
            self.menhir_pos = FunnyController.MENHIR_NOT_FOUND_LOCATION

        distances = dijkstra(self.arena, Coords(*self.menhir_pos), self.facing)
        distances_map = {hideout: distances[r(hideout)] for hideout in SAFE_POS}
        hideout = min(distances_map, key=distances_map.get)
        to_hidout_map = dijkstra(self.arena, hideout, self.facing)

        self.compute_actions(to_hidout_map, pos, self.facing)

    def _run_from_mist(self, pos):
        if self.menhir_pos is None:
            self.menhir_pos = FunnyController.MENHIR_NOT_FOUND_LOCATION

        to_menhir_map = dijkstra(self.arena, Coords(*self.menhir_pos), self.facing)
        self.compute_actions(to_menhir_map, pos, self.facing, FunnyController.RUN_DELAY)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.ep_it += 1
        if self.ep_it == FunnyController.START_RUNNING_FROM_MIST and self.strategy_iter < 4:
            self.strategy_iter = 4

        if self.facing is None:
            self.facing = FunnyController._get_facing(knowledge)

        if self.menhir_pos is None:
            for pos, tile in knowledge.visible_tiles.items():
                if tile.type == 'menhir':
                    self.menhir_pos = pos
                    if self.strategy_iter == 1:
                        self.actions = None
                    break
                self.empty_tiles.discard(pos)

        if self.actions is None:
            if self.strategy_iter == 0:
                self._find_weapon(knowledge.position)
            elif self.strategy_iter == 1:
                if self.menhir_pos != None:
                    self.strategy_iter += 1
                else:
                    self._find_menhir(knowledge.position)

            if self.strategy_iter == 2:
                self._hide(knowledge.position)
            elif self.strategy_iter == 4:
                self._run_from_mist(knowledge.position)

        if self.actions and self.action_iter < len(self.actions):
            action = self.actions[self.action_iter]

            self.action_iter += 1
            if self.action_iter == len(self.actions):
                if self.strategy_iter in [0, 2, 4]:
                    self.strategy_iter += 1
                self.actions = None
        else:
            action = self._hold_pos(knowledge)

        if action == characters.Action.STEP_FORWARD:
            self._reset_surrounding_walls()
        elif action == characters.Action.TURN_RIGHT:
            self.facing = self.facing.turn_right()
        elif action == characters.Action.TURN_LEFT:
            self.facing = self.facing.turn_left()

        return action

    @property
    def name(self) -> str:
        return f'FunnyController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET


POTENTIAL_CONTROLLERS = [
    FunnyController()
]
