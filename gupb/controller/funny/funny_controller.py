from gupb.controller.funny.commons import *
from gupb.controller.funny.pathing import dijkstra, create_path, get_next_move

SAFE_POS = [
    Coords(6, 6),
    Coords(6, 12),
    Coords(12, 6),
    Coords(12, 12)
]


class FunnyController:
    START_RUNNING_FROM_MIST = 220

    def __init__(self):
        with open("resources/arenas/isolated_shrine.gupb", "r") as f:
            self.arena = f.read().split("\n")[:-1]

        self.reset(None)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FunnyController):
            return True
        return False

    def __hash__(self) -> int:
        return 57

    FACING_DELTAS = {
        characters.Facing.UP: [(x, y) for x in range(-2, 3) for y in range(-4, 1)],
        characters.Facing.DOWN: [(x, y) for x in range(-2, 3) for y in range(0, 5)],
        characters.Facing.LEFT: [(x, y) for x in range(-4, 1) for y in range(-2, 3)],
        characters.Facing.RIGHT: [(x, y) for x in range(0, 5) for y in range(-2, 3)]
    }

    AXE_RANGE = {
        characters.Facing.UP: [(0, -1), (-1, -1), (1, -1)],
        characters.Facing.DOWN: [(0, 1), (-1, 1), (1, 1)],
        characters.Facing.LEFT: [(-1, 0), (-1, -1), (-1, 1)],
        characters.Facing.RIGHT: [(1, 0), (1, -1), (1, 1)]
    }

    SWORD_RANGE = {
        characters.Facing.UP: [(0, -i) for i in range(1, 4)],
        characters.Facing.DOWN: [(0, i) for i in range(1, 4)],
        characters.Facing.LEFT: [(-i, 0) for i in range(1, 4)],
        characters.Facing.RIGHT: [(i, 0) for i in range(1, 4)]
    }

    def _reset_surrounding_walls(self):
        self.surrounding_walls = {
            characters.Facing.UP: 0,
            characters.Facing.DOWN: 0,
            characters.Facing.LEFT: 0,
            characters.Facing.RIGHT: 0
        }

    def reset(self, arena_description) -> None:
        self.ep_it = 0
        self.facing = None
        self.strategy_iter = 0  # 0-find weapon, 1-hide, 3-go to mehnir
        self._reset_surrounding_walls()

        self.menhir_pos = Coords(9, 9)

        self.curr_target = None
        self.path = []

        self.weapon = "A"
        self.opponent_pos = None
        self.weapon_drops = set()

    def _get_tiles_in_range(self, pos):
        if self.weapon == "K":
            return s(pos, self.facing.value)
        else:
            return [s(pos, delta) for delta in FunnyController.AXE_RANGE[self.facing]]

    def _find_weapon(self, pos):
        y_max = len(self.arena)
        x_max = len(self.arena[0])

        weapon_types = ['A']
        weapons = []

        for y in range(y_max):
            for x in range(x_max):
                tile = self.arena[y][x]
                if tile in weapon_types:
                    weapons.append(Coords(x, y))

        distances, parents = dijkstra(self.arena, pos, self.facing)
        distance_map = {pos: distances[r(pos)] for pos in weapons}
        weapon = min(distance_map, key=distance_map.get)

        return create_path(pos, weapon, parents)

    def _hide(self, pos):
        distances, parents = dijkstra(self.arena, pos, self.facing, self.weapon_drops)
        distances_map = {hideout: distances[r(hideout)] for hideout in SAFE_POS}
        hideout = min(distances_map, key=distances_map.get)

        return create_path(pos, hideout, parents)

    def _hold_pos(self, knowledge: characters.ChampionKnowledge):
        pos = knowledge.position

        self.surrounding_walls[self.facing] = \
            -1 if self.arena[pos.y + self.facing.value.y][pos.x + self.facing.value.x] != '.' else 1

        turn = characters.Action.TURN_RIGHT
        if (self.facing == characters.Facing.UP and self.surrounding_walls[characters.Facing.LEFT] != -1) or \
                (self.facing == characters.Facing.LEFT and self.surrounding_walls[characters.Facing.DOWN] != -1) or\
                (self.facing == characters.Facing.DOWN and self.surrounding_walls[characters.Facing.RIGHT] != -1) or \
                (self.facing == characters.Facing.RIGHT and self.surrounding_walls[characters.Facing.UP] != -1):
            turn = characters.Action.TURN_LEFT

        return turn

    def _get_dangerous_fields(self, enemy_pos, knowledge):
        danger_tiles = [enemy_pos]

        enemy_weapon = knowledge.visible_tiles[enemy_pos].character.weapon

        if enemy_weapon == "amulet":
            danger_tiles.extend([s(enemy_pos, delta) for delta in [(-1, -1), (-1, 1), (1, -1), (1, 1)]])
        else:
            for facing in characters.Facing:
                if enemy_weapon == "knife":
                    danger_tiles.append(s(enemy_pos, facing.value))
                elif enemy_weapon == "bow":
                    danger_tiles.extend([s(enemy_pos,(i * facing.value[0], i * facing.value[1]))
                                         for i in range(1, 20)])
                elif enemy_weapon == "sword":
                    danger_tiles.extend([s(enemy_pos, delta) for delta in FunnyController.SWORD_RANGE[facing]])
                else:
                    danger_tiles.extend([s(enemy_pos, delta) for delta in FunnyController.AXE_RANGE[facing]])

        return danger_tiles

    def _fight(self, pos, danger_tiles):
        distances, parents = dijkstra(self.arena, pos, self.facing, set(danger_tiles).update(self.weapon_drops))
        weak_spots = [s(self.opponent_pos, t) for t in
                      [(-1, -1), (-1, 1), (1, -1), (1, 1)]]

        closest_weak_spot = sorted(weak_spots, key=lambda p: distances[r(p)])[0]

        return create_path(pos, closest_weak_spot, parents)

    def _go_to_menhir(self, pos):
        distances, parents = dijkstra(self.arena, pos, self.facing, self.weapon_drops)
        return create_path(pos, self.menhir_pos, parents)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.facing is None:
            self.facing = knowledge.visible_tiles.get(knowledge.position).character.facing

        pos = knowledge.position

        self.ep_it += 1
        if self.ep_it > FunnyController.START_RUNNING_FROM_MIST:
            self.strategy_iter = 3

        tiles_in_range = self._get_tiles_in_range(pos)
        for tile in tiles_in_range:
            try:
                character = knowledge.visible_tiles[tile].character
                if character is not None:
                    if character.health <= 2:
                        self.weapon_drops.add(tile)
                    return characters.Action.ATTACK
            except KeyError:
                pass

        if len(self.path) == 0:
            if self.strategy_iter == 0:
                self.path = self._find_weapon(pos)
            elif self.strategy_iter == 1:
                self.path = self._hide(pos)
            elif self.strategy_iter == 3:
                self.path = self._go_to_menhir(pos)

        if self.strategy_iter != 2:
            opposing_characters_pos = []
            for delta in FunnyController.FACING_DELTAS[self.facing]:
                try:
                    curr_pos = s(pos, delta)
                    if curr_pos != pos and knowledge.visible_tiles[curr_pos].character is not None:
                        opposing_characters_pos.append(curr_pos)
                except KeyError:
                    pass

            if len(opposing_characters_pos) > 0:
                opponent = sorted(opposing_characters_pos, key=lambda x: dist(x, pos))[0]
                danger_tiles = self._get_dangerous_fields(opponent, knowledge)

                for tile in self.path:
                    if tile in danger_tiles:
                        self.opponent_pos = opponent
                        self.path = self._fight(pos, danger_tiles)
                        break

        if len(self.path) == 0:
            action = self._hold_pos(knowledge)
        else:
            action = get_next_move(pos, self.facing, self.path[-1])
            if action == characters.Action.STEP_FORWARD:
                self.path.pop()
                if len(self.path) == 0:
                    if self.opponent_pos != None:
                        self.opponent_pos = None
                    else:
                        self.strategy_iter += 1

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
