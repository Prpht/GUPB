from gupb import controller
from gupb.controller.funny.commons import *
from gupb.controller.funny.pathing import dijkstra, create_path, get_next_move
from gupb.model import weapons
from gupb.model.arenas import Arena
from gupb.model.characters import CHAMPION_STARTING_HP
from gupb.model.effects import Mist


class FunnyController(controller.Controller):
    START_RUNNING_FROM_MIST = 220

    def __init__(self):
        pass

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
        self.menhir_pos = arena.menhir_position #Coords(9, 9)
        self.weapon_tiles = {coords: WEAPON_CODING[tile.loot.description().name]
                                 for coords, tile in self.terrain.items() if tile.loot is not None}
        with open(f"resources/arenas/{arena_description.name}.gupb", "r") as f:
            self.arena = f.read().split("\n")[:-1]
        self.safe_pos = SAFE_POS[arena_description.name]
        self.weapon_priority = WEAPON_PRIORITY[arena_description.name]
        self.not_menhir_tiles = set()
        for y in range(len(self.arena)):
            for x in range(len(self.arena[0])):
                if self.arena[y][x] == '.':
                    self.not_menhir_tiles.add((x, y))

        self.misted_tiles = set()
        self.hp = CHAMPION_STARTING_HP
        self.ep_it = 0
        self.facing = None
        self.strategy_iter = 0  # 0-find weapon, 1-find menhir, 2-hide, 4-go to menhir
        self._reset_surrounding_walls()

        self.curr_target = None
        self.path = []

        self.weapon = "K"
        self.opponent_pos = None
        self.weapon_drops = set()

    def praise(self, score: int) -> None:
        pass

    def _get_weaponable_tiles(self, pos, facing, weapon):
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
            self.not_menhir_tiles = set()
        else:
            self.not_menhir_tiles -= self.misted_tiles

    def _find_weapon(self, pos):
        weapon_types = [weapon for weapon, priority in self.weapon_priority.items() if priority == 5]
        weapons = list(filter(lambda x: self.weapon_tiles[x] in weapon_types, self.weapon_tiles))

        distances, parents = dijkstra(self.arena, pos, self.facing)
        distance_map = {pos: distances[r(pos)] for pos in weapons}
        weapon = min(distance_map, key=distance_map.get)

        return create_path(pos, weapon, parents)

    def _find_menhir(self, pos):
        distances, parents = dijkstra(self.arena, pos, self.facing)
        distance_map = {pos: distances[r(pos)] for pos in self.not_menhir_tiles}
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

        enemy = knowledge.visible_tiles[enemy_pos].character
        danger_tiles.extend(self._get_weaponable_tiles(enemy_pos, enemy.facing, enemy.weapon))
        return danger_tiles

    def _run_away(self, pos, danger_tiles):
        return []

    def _worse_weapon_tiles(self):
        worse_weapon_tiles = set()
        current_weapon_priority = self.weapon_priority[self.weapon]
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
        weak_spots = [s(self.opponent_pos, t) for t in
                      [(-1, -1), (-1, 1), (1, -1), (1, 1)]]
        weak_spots = list(filter(lambda x: self.arena[x[1]][x[0]] not in ['=', '#'], weak_spots))
        if not weak_spots:
            print("no weak spots")
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

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self_knowledge = knowledge.visible_tiles.get(knowledge.position).character
        if self.menhir_pos is None and self.strategy_iter > 2:
            self.strategy_iter = 2
        if self.facing is None:
            self.facing = self_knowledge.facing
        self.weapon = WEAPON_CODING[self_knowledge.weapon.name]
        # if self_knowledge.health < self.hp:
        #     self.hp = self_knowledge.health
            ### ogarnac kto bije, reakcja
        pos = knowledge.position

        self.ep_it += 1
        if self.ep_it > FunnyController.START_RUNNING_FROM_MIST:
            print("change strategy iter to 4")
            self.strategy_iter = 4
        visible_tiles = knowledge.visible_tiles
        # TODO uwaga na to, czasochłonne
        # self._update_misted_tiles(visible_tiles)
        for tile in self.weapon_tiles:
            if tile in visible_tiles and not visible_tiles[tile].character:
                try:
                    self._update_weapons_knowledge(tile, visible_tiles[tile].loot.name)
                except Exception as e:
                    print(e, "a")

        tiles_in_range = self._get_weaponable_tiles(pos, self.facing, self.weapon)
        for tile in tiles_in_range:
            try:
                tile_knowledge = knowledge.visible_tiles[tile]
                if tile_knowledge.loot and tile not in self.weapon_tiles:
                    print("found it!")
                    self._update_weapons_knowledge(tile, tile_knowledge.loot.name)
                character = tile_knowledge.character
                if character is not None: ## dolozyc ze jesli ja nie jestem w jego zasiegu albo jestem ale
                                            # mam wystarczajaco duzo zycia
                    print("attack")
                    if character.health <= 2:
                        try:
                            self._update_weapons_knowledge(tile, character.weapon.name)
                            print("added " + character.weapon.name)
                        except Exception as e:
                            print(e)
                        self.weapon_drops.add(tile)
                    return characters.Action.ATTACK
            except KeyError:
                pass
        print(f"Path len: {len(self.path)}, strategy iter: {self.strategy_iter}")
        if len(self.path) == 0:
            if self.strategy_iter == 0:
                print("Find weapon")
                self.path = self._find_weapon(pos)
            elif self.strategy_iter == 1:
                print("Find menhir")
                self._update_menhir_knowledge(visible_tiles)
                self.path = self._find_menhir(pos)

            elif self.strategy_iter == 2:
                print("Hide")
                self.path = self._hide(pos)
            elif self.strategy_iter == 4:
                print("Menhir go")
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
                        print("Fight")
                        self.opponent_pos = opponent
                        self.path = self._fight(pos, danger_tiles)
                        break

        if len(self.path) == 0:
            # if self.strategy_iter < 4 and self.weapon_priority[self.weapon] < 4:
            #     print("Find weapon cause bad weapon")
            #     self.path = self._find_weapon(pos)
            # else:
            print("Hold pos")
            action = self._hold_pos(knowledge)
        else:
            action = get_next_move(pos, self.facing, self.path[-1])
            print("action: ", action)
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

    @property
    def name(self) -> str:
        return f'FunnyController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET


POTENTIAL_CONTROLLERS = [
    FunnyController()
]
