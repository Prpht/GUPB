from typing import Dict, Tuple, List
from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.grid import Grid
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.arenas import Arena, ArenaDescription
from gupb.model.characters import ChampionDescription, Facing, Action, ChampionKnowledge
from gupb.model.coordinates import Coords
from gupb.model.games import MIST_TTH
from gupb.model.tiles import Menhir, Wall, Sea, Land, TileDescription
from gupb.model.weapons import Knife, Sword, Bow, Axe, Amulet, WeaponDescription
from queue import SimpleQueue

FIELD_WEIGHT = 100

TILES = [Land, Sea, Wall, Menhir]

TILES_MAP = {tile().description().type: tile for tile in TILES}

WEAPONS = [(Knife, 100), (Sword, 25), (Bow, 1), (Axe, 10), (Amulet, 25)]
WEAPONS.sort(key=lambda x: x[1])

WEAPONS_MAP = {weapon().description(): weapon for weapon, _ in WEAPONS}

WEAPONS_ENCODING = {weapon().description(): value for weapon, value in WEAPONS}

finder = AStarFinder()

FIELD_ATTACKED = FIELD_WEIGHT * FIELD_WEIGHT

WEAPONS_PRIORITY = [weapon[0]().description() for weapon in WEAPONS]


def points_dist(cord1, cord2):
    return int(((cord1.x - cord2.x) ** 2 +
                (cord1.y - cord2.y) ** 2) ** 0.5)


def get_first_possible_move(moves: List[Tuple[Action, int]]):
    return next((next_move for next_move in moves if next_move[0] != Action.DO_NOTHING), (Action.DO_NOTHING, -1))


class ArenaMapped(Arena):
    def __init__(self, arena_description: ArenaDescription):
        arena = Arena.load(arena_description.name)
        super().__init__(arena.name, arena.terrain)
        self.menhir_position = arena_description.menhir_position
        self.terrain[arena_description.menhir_position] = Menhir()
        self.tiles_memory: Dict[Coords, TileDescription] = {}
        self.tiles_age: Dict[Coords, int] = {}
        self.current_terrain: Dict[Coords, TileDescription] = {k: v.description() for k, v in
                                                               arena.terrain.items()}
        self.champions: Dict[
            ChampionDescription, Tuple[Coords, int]] = {}  # second value is the age when champ was seen
        self.matrix = []
        self.champion: ChampionDescription = None
        self.position: Coords = None
        self.episode: int = 0
        self.effect_weight: int = FIELD_ATTACKED
        self.can_hit: bool = False
        x_size, y_size = self.size
        self.terrain_matrix = [[FIELD_WEIGHT for _ in range(y_size)] for _ in range(x_size)]
        for position, tile in self.terrain.items():
            y, x = position  # to work it have to be swapped, don't know why
            if not tile.terrain_passable():
                self.terrain_matrix[x][y] = 0

    def register_effect(self, _, coords: Coords) -> None:
        y, x = coords
        self.matrix[x][y] = self.effect_weight

    def get_next_field(self) -> Coords:
        return self.position + self.champion.facing.value

    def get_left_field(self):
        return self.position + self.champion.facing.turn_left().value

    def get_right_field(self):
        return self.position + self.champion.facing.turn_right().value

    def increase_mist(self) -> None:
        self.mist_radius -= 1 if self.mist_radius > 0 else self.mist_radius
        if self.mist_radius:
            for coords in self.terrain:
                distance = points_dist(coords, self.menhir_position)
                if distance == self.mist_radius:
                    y, x = coords
                    self.terrain_matrix[x][y] = -1

    def prepare_matrix(self, knowledge: characters.ChampionKnowledge) -> None:
        self.tiles_age = {**{k: v + 1 for k, v in self.tiles_age.items()},
                          **{k: 0 for k in knowledge.visible_tiles.keys()}}
        self.champions = {champ: (tere[0], tere[1] + 1) for champ, tere in self.champions.items()}
        self.tiles_memory = {**self.tiles_memory, **knowledge.visible_tiles}
        self.champion = knowledge.visible_tiles.get(knowledge.position).character
        self.position = knowledge.position
        self.current_terrain = {**{k: v.description() for k, v in
                                   self.terrain.items()}, **self.tiles_memory}
        self.can_hit = False
        self.matrix = self.terrain_matrix.copy()
        next_field = self.get_next_field()
        if self.matrix[next_field[1]][next_field[0]] > 0:
            self.matrix[next_field[1]][next_field[0]] = FIELD_WEIGHT / 2
        used_weapon = WEAPONS_ENCODING.get(self.champion.weapon)

        if self.episode % MIST_TTH == 0:
            self.increase_mist()
        self.episode += 1

        for position, tileDescription in knowledge.visible_tiles.items():
            if tileDescription.character and tileDescription.character != self.champion:
                self.champions[tileDescription.character] = (position, 0)

        for position, tileDescription in self.current_terrain.items():
            y, x = position  # to work it have to be swapped, don't know why
            if tileDescription.loot:
                importance = WEAPONS_ENCODING.get(tileDescription.loot)
                if importance > used_weapon:
                    self.matrix[x][y] = importance
                else:
                    self.matrix[x][y] *= importance

        seen_champs = {}

        for character, tere in self.champions.items():
            position, age = tere

            y, x = position
            if age == 0:
                self.matrix[x][y] = -2
                seen_champs[position] = True
            else:
                self.matrix[x][y] = FIELD_ATTACKED / age

            aged_value = int(FIELD_ATTACKED / (age + 1))
            self.effect_weight = max(aged_value, FIELD_WEIGHT)
            weapon = WEAPONS_MAP.get(character.weapon)
            weapon.cut(self, position, character.facing)
            self.effect_weight = max(aged_value / 2, FIELD_WEIGHT)
            weapon.cut(self, position, character.facing.turn_left())

        def check_if_hit(_, coords: Coords) -> None:
            if coords in seen_champs:
                self.can_hit = True

        tmp = self.register_effect
        self.register_effect = check_if_hit
        weapon = WEAPONS_MAP.get(self.champion.weapon)
        weapon.cut(self, self.position, self.champion.facing)
        self.register_effect = tmp

    def calc_mist_dist(self):
        return self.mist_radius - points_dist(self.position, self.menhir_position)

    def find_move_to(self, end_position: Coords) -> Tuple[Action, int]:
        action = Action.DO_NOTHING
        length = 0
        if end_position == self.position:
            return action, length
        grid = Grid(matrix=self.matrix)
        start = grid.node(*self.position)
        end = grid.node(*end_position)
        path, _ = finder.find_path(start, end, grid)
        # print(grid.grid_str(path=path, start=start, end=end))
        if len(path) <= 0:
            return action, -1
        else:
            if self.get_next_field() == path[1]:
                action = Action.STEP_FORWARD
                length += 1
            elif self.get_right_field() == path[1]:
                action = Action.TURN_RIGHT
                length += 2
            elif self.get_left_field() == path[1]:
                action = Action.TURN_LEFT
                length += 2
            else:
                action = Action.TURN_LEFT
                length += 3
            if len(path) > 2:
                for idx, field in enumerate(path[2:]):
                    prev_field = path[idx]  # cords of field 2 turns ago
                    if prev_field[0] != field[0] and prev_field[1] != field[1]:  # it means that turning is needed
                        length += 2
                    else:
                        length += 1
            return action, length

    def find_best_move(self, coords: List[Coords]) -> Tuple[Action, int]:
        potencial_actions = [self.find_move_to(postion) for postion in
                             coords]
        filterd_actions = [(action, length) for action, length in potencial_actions if length != -1]
        if len(filterd_actions) == 0:
            return Action.DO_NOTHING, -1
        return min(filterd_actions, key=lambda x: x[1])

    def find_move_to_menhir(self) -> Tuple[Action, int]:
        menhir_positions = [self.menhir_position + possible_postion.value for possible_postion in Facing]
        menhir_positions = [(len(self.check_position_surrounding(cord)), cord) for cord in menhir_positions if
                            self.terrain[cord].terrain_passable()]
        menhir_positions.sort()
        values = set(map(lambda x: x[0], menhir_positions))
        menhir_positions = [[y[1] for y in menhir_positions if y[0] == x] for x in values]
        if self.position in menhir_positions[0]:
            # todo: change it into const
            return Action.DO_NOTHING, -1
        menhir_positions = [self.find_best_move(grouped_menhir_position)
                            for grouped_menhir_position in menhir_positions]
        return get_first_possible_move(menhir_positions)

    def find_move_to_nearest_weapon(self, weapon: WeaponDescription) -> Tuple[Action, int]:
        bows_positions = [position for position, tileDescription in self.current_terrain.items() if
                          tileDescription.loot == weapon and position != self.position]
        return self.find_best_move(bows_positions)

    def get_field_value(self, coords: Coords):
        y, x = coords
        return self.matrix[x][y]

    def check_if_passable_safely(self, coords: Coords) -> bool:
        value = self.get_field_value(coords)
        return value != FIELD_ATTACKED and value > 0

    def find_escape_action(self) -> Action:
        if self.check_if_passable_safely(self.get_left_field()):
            return Action.TURN_LEFT
        elif self.check_if_passable_safely(self.get_right_field()):
            return Action.TURN_RIGHT
        elif self.check_if_passable_safely(self.get_next_field()):
            return Action.STEP_FORWARD
        return Action.DO_NOTHING

    def is_field_safe(self, coord: Coords, facing: Coords):
        safe = True
        x, y = self.size
        while safe:
            coord += facing
            if coord[0] < 0 or coord[1] < 0 or coord[0] >= x or coord[1] >= y:
                break
            if self.terrain[coord].terrain_passable():
                safe = False
        return safe

    def check_position_surrounding(self, coords: Coords):
        x, y = coords
        neighbors = [Coords(x2, y2) for x2 in range(x - 1, x + 2)
                     for y2 in range(y - 1, y + 2)
                     if x != x2 or y != y2]
        return [coord for coord in neighbors if
                self.terrain[coord].terrain_transparent() and not self.is_field_safe(coords, coord - coords)]

    def find_scan_action(self) -> Action:
        suraunding = self.check_position_surrounding(self.position)
        direct_surdoding = [cord.value + self.position for cord in Facing]
        suraunding = [(self.tiles_age[cords], cords) for cords in suraunding if cords in direct_surdoding]
        suraunding.sort(reverse=True)
        suraunding = [x[1] for x in suraunding]
        if len(suraunding) == 1:
            if self.position + self.champion.facing.value not in suraunding:
                return Action.TURN_LEFT
            return Action.DO_NOTHING
        if self.get_right_field() == suraunding[0]:
            return Action.TURN_RIGHT
        if self.get_left_field() == suraunding[0]:
            return Action.TURN_LEFT
        if self.get_right_field() == suraunding[1]:
            return Action.TURN_RIGHT
        if self.get_left_field() == suraunding[1]:
            return Action.TURN_LEFT
        return Action.TURN_LEFT


class ShallowMindController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.prev_champion: ChampionDescription = None
        self.arena: ArenaMapped = None
        self.action_queue: SimpleQueue[Action] = SimpleQueue()
        self.bow_taken = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ShallowMindController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: ArenaDescription) -> None:
        self.arena = ArenaMapped(arena_description)
        self.bow_taken = False

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self.prev_champion = self.arena.champion
        self.arena.prepare_matrix(knowledge)
        if not self.action_queue.empty():
            return self.action_queue.get()
        champ = self.arena.champion
        if self.arena.can_hit:
            return Action.ATTACK
        if self.arena.calc_mist_dist() > 5:
            if champ.weapon != WEAPONS_PRIORITY[0]:
                action, _ = self.arena.find_move_to_nearest_weapon(WEAPONS_PRIORITY[0])
                if action != Action.DO_NOTHING:
                    return action
                elif champ.weapon == WEAPONS_PRIORITY[-1]:
                    weapons = [self.arena.find_move_to_nearest_weapon(weapon) for weapon in WEAPONS_PRIORITY]
                    action, _ = get_first_possible_move(weapons)
                    if action != Action.DO_NOTHING:
                        return action
        # todo this need to be redone
        if self.prev_champion:
            if champ.health != self.prev_champion.health:
                action = self.arena.find_escape_action()
                if action != Action.DO_NOTHING:
                    self.action_queue.put(Action.STEP_FORWARD)
                    return action
        action, length = self.arena.find_move_to_menhir()
        if action == Action.DO_NOTHING:
            return self.arena.find_scan_action()
        return action

    @property
    def name(self) -> str:
        return f'ShallowMindController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREY


POTENTIAL_CONTROLLERS = [
    ShallowMindController('test'),
]
