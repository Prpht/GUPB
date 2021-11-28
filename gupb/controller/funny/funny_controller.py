from gupb import controller
from gupb.controller.funny.commons import *
from gupb.controller.funny.pathing import dijkstra, create_path, get_next_move
from gupb.model import weapons
from gupb.model.arenas import Arena
from gupb.model.characters import CHAMPION_STARTING_HP
from gupb.model.effects import Mist
from gupb.model.profiling import profile
import random


class FunnyController(controller.Controller):
    START_RUNNING_FROM_MIST = 550

    def __init__(self):
        self.strategies = {
            'original_funny_controller_strategy': self.original_funny_controller_strategy,
            'menhir_camping_strategy': self.menhir_camping_strategy,
            'hide_in_safe_spot_strategy': self.hide_in_safe_spot_strategy
        }
        self.Q = {strategy: 100.0 for strategy in self.strategies}
        self.N = {strategy: 0 for strategy in self.strategies}
        self.epsilon = 0.1

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

    def _reset_surrounding_walls(self):
        self.surrounding_walls = {
            characters.Facing.UP: 0,
            characters.Facing.DOWN: 0,
            characters.Facing.LEFT: 0,
            characters.Facing.RIGHT: 0
        }

    def reset(self, arena_description) -> None:
        arena = Arena.load(arena_description.name)
        self.terrain = arena.terrain
        self.menhir_pos = arena.menhir_position
        self.weapon_tiles = {coords: WEAPON_CODING[tile.loot.description().name]
                                 for coords, tile in self.terrain.items() if tile.loot is not None}
        with open(f"resources/arenas/{arena_description.name}.gupb", "r") as f:
            self.arena = f.read().split("\n")[:-1]
        self.safe_pos = SAFE_POS[arena_description.name]
        self.weapon_priority = WEAPON_PRIORITY[arena_description.name]
        self.to_check_if_menhir_tiles = set()
        for y in range(len(self.arena)):
            for x in range(len(self.arena[0])):
                if self.arena[y][x] == '.':
                    self.to_check_if_menhir_tiles.add((x, y))

        self.current_strategy = random.choice(list(self.strategies.keys())) if random.random() < self.epsilon \
            else max(self.Q, key=self.Q.get)
        self.misted_tiles = set()
        self.hp = CHAMPION_STARTING_HP
        self.ep_it = 0
        self.facing = None
        self.strategy_iter = 0  # 0-find weapon, 1-find menhir, 2-hide, 4-go to menhir
        self._reset_surrounding_walls()

        self.curr_target = None
        self.path = []

        self.weapon = "knife"
        self.opponent_pos = None
        self.weapon_drops = set()
        #print(self.current_strategy)
        #print(self.Q)
        #print(self.N)

    def praise(self, score: int) -> None:
        self.N[self.current_strategy] += 1
        self.Q[self.current_strategy] += 1.0/self.N[self.current_strategy] * (score - self.Q[self.current_strategy])

    def _get_weaponable_tiles(self, pos, facing, weapon_name):
        weapon = WEAPON_CODING[weapon_name]
        pos = Coords(x=pos[0], y=pos[1])
        if weapon == 'K':
            weaponable_tiles = weapons.Knife.cut_positions(self.terrain, pos, facing)
        elif weapon == 'S':
            weaponable_tiles = weapons.Sword.cut_positions(self.terrain, pos, facing)
        elif weapon == 'B':
            weaponable_tiles = weapons.Bow.cut_positions(self.terrain, pos, facing)
        elif weapon == 'M':
            weaponable_tiles = weapons.Amulet.cut_positions(self.terrain, pos, facing)
        else:
            weaponable_tiles = weapons.Axe.cut_positions(self.terrain, pos, facing)
        return weaponable_tiles

    def _update_misted_tiles(self, visible_tiles: characters.ChampionKnowledge.visible_tiles):
        misted_tiles = set(filter(lambda x: visible_tiles[x].effects and Mist in visible_tiles[x].effects,
                                   visible_tiles))
        ### zupdatować płytki które są też na pewno zamglone na podst widocznych mgieł
        self.misted_tiles.update(misted_tiles)

    def _update_menhir_knowledge(self, visible_tiles: characters.ChampionKnowledge.visible_tiles):
        menhir_tile = list(filter(lambda x: visible_tiles[x].type == 'menhir', visible_tiles))
        if menhir_tile:
            self.menhir_pos = menhir_tile[0]
        else:
            self.to_check_if_menhir_tiles -= set(visible_tiles.keys())
            self.to_check_if_menhir_tiles -= self.misted_tiles

    def _find_weapon(self, pos):
        weapon_types = [weapon for weapon, priority in self.weapon_priority.items() if priority == 5]
        weapons = list(filter(lambda x: self.weapon_tiles[x] in weapon_types, self.weapon_tiles))

        distances, parents = dijkstra(self.arena, pos, self.facing)
        distance_map = {pos: distances[r(pos)] for pos in weapons}
        weapon = min(distance_map, key=distance_map.get)

        return create_path(pos, weapon, parents)

    def _find_menhir(self, pos):
        distances, parents = dijkstra(self.arena, pos, self.facing, self._worse_weapon_tiles())
        distance_map = {pos: distances[r(pos)] for pos in self.to_check_if_menhir_tiles}
        tile = min(distance_map, key=distance_map.get)

        return create_path(pos, tile, parents)

    def _hide(self, pos):
        #distances, parents = dijkstra(self.arena, pos, self.facing, self.weapon_drops)
        distances, parents = dijkstra(self.arena, pos, self.facing, self._worse_weapon_tiles())
        distances_map = {hideout: distances[r(hideout)] for hideout in self.safe_pos}
        hideout = min(distances_map, key=distances_map.get)

        return create_path(pos, hideout, parents)

    def _hold_pos(self, knowledge: characters.ChampionKnowledge):
        pos = knowledge.position

        self.surrounding_walls[self.facing] = \
            -1 if self.arena[pos.y + self.facing.value.y][pos.x + self.facing.value.x] not in ['.', '='] else 1

        turn = characters.Action.TURN_RIGHT
        if (self.facing == characters.Facing.UP and self.surrounding_walls[characters.Facing.LEFT] != -1) or \
                (self.facing == characters.Facing.LEFT and self.surrounding_walls[characters.Facing.DOWN] != -1) or\
                (self.facing == characters.Facing.DOWN and self.surrounding_walls[characters.Facing.RIGHT] != -1) or \
                (self.facing == characters.Facing.RIGHT and self.surrounding_walls[characters.Facing.UP] != -1):
            turn = characters.Action.TURN_LEFT

        return turn

    def _get_dangerous_fields(self, enemy_pos, knowledge):
        danger_tiles = [enemy_pos]

        enemy = knowledge.visible_tiles[enemy_pos].character
        danger_tiles.extend(self._get_weaponable_tiles(enemy_pos, enemy.facing, enemy.weapon.name))
        return danger_tiles

    def _run_away(self, pos, danger_tiles):
        distances, parents = dijkstra(self.arena, pos, self.facing, danger_tiles)
        surrounding_tiles = [(pos[0]+i, pos[1]+j) for i in range(-4, 5) for j in range(-4, 5)
                             if 0 <= pos[0]+i < len(self.arena[0]) and 0 <= pos[1]+j < len(self.arena)]
        surrounding_tiles.remove(pos)
        surrounding_tiles = list(filter(lambda x: self.arena[x[1]][x[0]] not in ['=', '#'], surrounding_tiles))

        distances_map = {hideout: distances[r(hideout)] for hideout in surrounding_tiles}
        hideout = min(distances_map, key=distances_map.get)
        return create_path(pos, hideout, parents)

    def _worse_weapon_tiles(self):
        worse_weapon_tiles = set()
        current_weapon_priority = self.weapon_priority[WEAPON_CODING[self.weapon]]
        for tile, weapon in self.weapon_tiles.items():
            if self.weapon_priority[weapon] < current_weapon_priority:
                worse_weapon_tiles.add(tile)
        return worse_weapon_tiles

    def _update_weapons_knowledge(self, tile, weapon_name):
        code = WEAPON_CODING[weapon_name]
        self.weapon_tiles[tile] = code
        self.arena[tile[1]] = self.arena[tile[1]][:tile[0]] + \
                              code + \
                              self.arena[tile[1]][tile[0] + 1:]

    def _fight(self, pos, danger_tiles):
        danger_tiles_set = set(danger_tiles)
        # danger_tiles_set.update(self.weapon_drops)
        danger_tiles_set.update(self._worse_weapon_tiles())
        distances, parents = dijkstra(self.arena, pos, self.facing, danger_tiles_set)

        if WEAPON_CODING[self.weapon] in ['A', 'M']:
            weak_spots = [s(self.opponent_pos, t) for t in
                          [(-1, -1), (-1, 1), (1, -1), (1, 1)]]
        elif WEAPON_CODING[self.weapon] == 'S':
            weak_spots = [s(self.opponent_pos, t) for t in
                          [(-3, 0), (-2, 0), (3, 0), (2, 0), (0, -3), (0, -2), (0, 3), (0, 2)]]
        elif WEAPON_CODING[self.weapon] == 'B':
            ranged = [[(-i, 0), (i, 0), (0, -i), (0, i)] for i in range(4, 8)]
            ranged = [x for l in ranged for x in l]
            weak_spots = [s(self.opponent_pos, t) for t in ranged]
        else:
            weak_spots = [s(self.opponent_pos, t) for t in
                          [(-1, 0), (1, 0), (0, -1), (0, 1)]]

        weak_spots = list(filter(lambda x: self.arena[x[1]][x[0]] not in ['=', '#'], weak_spots))
        if not weak_spots:
            return []
        else:
            closest_weak_spot = sorted(weak_spots, key=lambda p: distances[r(p)])[0]
            return create_path(pos, closest_weak_spot, parents)

    def _go_to_menhir(self, pos):
        #distances, parents = dijkstra(self.arena, pos, self.facing, self.weapon_drops)
        distances, parents = dijkstra(self.arena, pos, self.facing, self._worse_weapon_tiles())
        if self.menhir_pos is None:
            # misted_tiles_coords = [coords for coords, _ in self.misted_tiles]
            self.menhir_pos = Coords(25, 25)
        return create_path(pos, self.menhir_pos, parents)

    def original_funny_controller_strategy(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        pos = knowledge.position
        visible_tiles = knowledge.visible_tiles
        tile = knowledge.visible_tiles[pos]
        self_knowledge = tile.character

        if tile.loot:
            self._update_weapons_knowledge(pos, tile.loot.name)
        self.weapon = self_knowledge.weapon.name

        if self.menhir_pos is None and self.strategy_iter > 1:
            self.strategy_iter = 1
        if self.facing is None:
            self.facing = self_knowledge.facing
        # if self_knowledge.health < self.hp:
        #     self.hp = self_knowledge.health
        ### ogarnac kto bije, reakcja

        self.ep_it += 1
        if self.ep_it > FunnyController.START_RUNNING_FROM_MIST:
            self.strategy_iter = 4

        # TODO uwaga na to, czasochłonne
        # self._update_misted_tiles(visible_tiles)
        for tile in self.weapon_tiles:
            if tile in visible_tiles and not visible_tiles[tile].character:
                self._update_weapons_knowledge(tile, visible_tiles[tile].loot.name)

        tiles_in_range = self._get_weaponable_tiles(pos, self.facing, self.weapon)
        for tile in tiles_in_range:
            try:
                tile_knowledge = knowledge.visible_tiles[tile]
                if tile_knowledge.loot and tile not in self.weapon_tiles:
                    self._update_weapons_knowledge(tile, tile_knowledge.loot.name)
                character = tile_knowledge.character
                if character is not None:  ## dolozyc ze jesli ja nie jestem w jego zasiegu albo jestem ale
                    # mam wystarczajaco duzo zycia
                    if character.health <= 2:
                        self._update_weapons_knowledge(tile, character.weapon.name)
                        self.weapon_drops.add(tile)
                    return characters.Action.ATTACK
            except KeyError:
                pass
        if len(self.path) == 0:
            if self.strategy_iter == 0:
                self.path = self._find_weapon(pos)
            elif self.strategy_iter == 1:
                self._update_menhir_knowledge(visible_tiles)
                self.path = self._find_menhir(pos)
            elif self.strategy_iter == 2:
                self.path = self._hide(pos)
            elif self.strategy_iter == 4:
                self.path = self._go_to_menhir(pos)

        if self.strategy_iter != 3:
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
                    if self.opponent_pos is not None:
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

    def menhir_camping_strategy(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """take bow or axe, run away from enemies, find menhir and stay there"""
        # 0-find weapon, 1-find menhir, 3-go to menhir
        pos = knowledge.position
        visible_tiles = knowledge.visible_tiles
        tile = knowledge.visible_tiles[pos]
        self_knowledge = tile.character

        if tile.loot:
            self._update_weapons_knowledge(pos, tile.loot.name)
        self.weapon = self_knowledge.weapon.name

        if self.facing is None:
            self.facing = self_knowledge.facing

        self.ep_it += 1
        if self.ep_it > FunnyController.START_RUNNING_FROM_MIST:
            self.strategy_iter = 3

        # self._update_misted_tiles(visible_tiles)
        for tile in self.weapon_tiles:
            if tile in visible_tiles and not visible_tiles[tile].character:
                self._update_weapons_knowledge(tile, visible_tiles[tile].loot.name)

        tiles_in_range = self._get_weaponable_tiles(pos, self.facing, self.weapon)
        for tile in tiles_in_range:
            try:
                tile_knowledge = knowledge.visible_tiles[tile]
                if tile_knowledge.loot and tile not in self.weapon_tiles:
                    self._update_weapons_knowledge(tile, tile_knowledge.loot.name)
                character = tile_knowledge.character
                if character is not None:  ## dolozyc ze jesli ja nie jestem w jego zasiegu albo jestem ale
                    # mam wystarczajaco duzo zycia
                    if character.health <= 2:
                        self._update_weapons_knowledge(tile, character.weapon.name)
                        self.weapon_drops.add(tile)
                    return characters.Action.ATTACK
            except KeyError:
                pass
        if len(self.path) == 0:
            if self.strategy_iter == 0:
                self.path = self._find_weapon(pos)
            elif self.strategy_iter < 3 and self.menhir_pos is None:
                self.strategy_iter = 1
                self._update_menhir_knowledge(visible_tiles)
                self.path = self._find_menhir(pos)
            elif self.strategy_iter == 3 or self.strategy_iter < 3 and self.menhir_pos is not None:
                self.path = self._go_to_menhir(pos)

        opposing_characters_pos = []
        for tile in visible_tiles:
            if tile == pos:
                continue
            if visible_tiles[tile].character is not None:
                opposing_characters_pos.append(tile)

        if len(opposing_characters_pos) > 0:
            danger_tiles = set()
            for opponent in opposing_characters_pos:
                danger_tiles.update(set(self._get_dangerous_fields(opponent, knowledge)))

            if pos in danger_tiles:
                self.path = self._run_away(pos, danger_tiles)

        if len(self.path) == 0:
            action = self._hold_pos(knowledge)
        else:
            action = get_next_move(pos, self.facing, self.path[-1])
            if action == characters.Action.STEP_FORWARD:
                self.path.pop()
                if len(self.path) == 0:
                    self.strategy_iter += 1

        if action == characters.Action.STEP_FORWARD:
            self._reset_surrounding_walls()
        elif action == characters.Action.TURN_RIGHT:
            self.facing = self.facing.turn_right()
        elif action == characters.Action.TURN_LEFT:
            self.facing = self.facing.turn_left()

        return action

    def hide_in_safe_spot_strategy(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """take bow or axe (to think if necessary), run away from enemies, go to safe place and stay there"""
        # 0-find weapon, 1-go to safe place
        pos = knowledge.position
        visible_tiles = knowledge.visible_tiles
        tile = knowledge.visible_tiles[pos]
        self_knowledge = tile.character

        if tile.loot:
            self._update_weapons_knowledge(pos, tile.loot.name)
        self.weapon = self_knowledge.weapon.name

        if self.facing is None:
            self.facing = self_knowledge.facing

        self.ep_it += 1

        # TODO uwaga na to, czasochłonne
        # self._update_misted_tiles(visible_tiles)
        for tile in self.weapon_tiles:
            if tile in visible_tiles and not visible_tiles[tile].character:
                self._update_weapons_knowledge(tile, visible_tiles[tile].loot.name)

        tiles_in_range = self._get_weaponable_tiles(pos, self.facing, self.weapon)
        for tile in tiles_in_range:
            try:
                tile_knowledge = knowledge.visible_tiles[tile]
                if tile_knowledge.loot and tile not in self.weapon_tiles:
                    self._update_weapons_knowledge(tile, tile_knowledge.loot.name)
                character = tile_knowledge.character
                if character is not None:  ## dolozyc ze jesli ja nie jestem w jego zasiegu albo jestem ale
                    # mam wystarczajaco duzo zycia
                    if character.health <= 2:
                        self._update_weapons_knowledge(tile, character.weapon.name)
                        self.weapon_drops.add(tile)
                    return characters.Action.ATTACK
            except KeyError:
                pass
        if len(self.path) == 0:
            if self.strategy_iter == 0:
                self._update_menhir_knowledge(visible_tiles)
                self.path = self._find_weapon(pos)
            elif self.strategy_iter == 1:
                if self.menhir_pos is not None:
                    self.path = self._go_to_menhir(pos)
                else:
                    self.path = self._hide(pos)

        opposing_characters_pos = []
        for tile in visible_tiles:
            if tile == pos:
                continue
            if visible_tiles[tile].character is not None:
                opposing_characters_pos.append(tile)

        if len(opposing_characters_pos) > 0:
            danger_tiles = set()
            for opponent in opposing_characters_pos:
                danger_tiles.update(set(self._get_dangerous_fields(opponent, knowledge)))

            if pos in danger_tiles:
                self.path = self._run_away(pos, danger_tiles)

        if len(self.path) == 0:
            action = self._hold_pos(knowledge)
        else:
            action = get_next_move(pos, self.facing, self.path[-1])
            if action == characters.Action.STEP_FORWARD:
                self.path.pop()
                if len(self.path) == 0:
                    self.strategy_iter += 1

        if action == characters.Action.STEP_FORWARD:
            self._reset_surrounding_walls()
        elif action == characters.Action.TURN_RIGHT:
            self.facing = self.facing.turn_right()
        elif action == characters.Action.TURN_LEFT:
            self.facing = self.facing.turn_left()

        return action

    @profile
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.strategies[self.current_strategy](knowledge)

    @property
    def name(self) -> str:
        return f'FunnyController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET


POTENTIAL_CONTROLLERS = [
    FunnyController()
]
