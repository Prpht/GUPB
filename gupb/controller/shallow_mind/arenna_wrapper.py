import copy
from typing import Dict, List
from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.grid import Grid

from gupb.controller.shallow_mind.consts import FIELD_ATTACKED, FIELD_WEIGHT, WEAPONS_ENCODING, WEAPONS_MAP
from gupb.controller.shallow_mind.utils import points_dist
from gupb.model import characters
from gupb.model.arenas import Arena, ArenaDescription
from gupb.model.characters import ChampionDescription, Facing, Action
from gupb.model.coordinates import Coords
from gupb.model.games import MIST_TTH
from gupb.model.tiles import Menhir, TileDescription
from gupb.model.weapons import WeaponDescription

finder = AStarFinder()


class DestinationWrapper:
    def __init__(self, destination: Coords, action: Action = Action.DO_NOTHING, time: int = -1):
        self.destination: Coords = destination
        self.action: Action = action
        self.time: int = time
        self.reachable: bool = time >= 0

    def __repr__(self):
        return f'<DestinationWrapper destination:{self.destination} action:{self.action} time:{self.time} reachable:{self.reachable}>'

    def __lt__(self, other):
        if not self.reachable:
            return False
        elif not other.reachable:
            return True
        return self.time < other.time


class ArenaWrapper(Arena):
    def __init__(self, arena_description: ArenaDescription):
        arena = Arena.load(arena_description.name)
        super().__init__(arena.name, arena.terrain)
        self.episode: int = 0
        # menhir properties
        self.menhir_position: Coords = arena_description.menhir_position
        self.menhir_destination: Coords = None
        self.move_to_menhir: DestinationWrapper = DestinationWrapper(self.menhir_position)
        # champ
        self.champion: ChampionDescription = None
        self.prev_champion: ChampionDescription = None
        self.position: Coords = None
        # mappings
        self.terrain[arena_description.menhir_position] = Menhir()
        self.terrain_description: Dict[Coords, TileDescription] = {k: v.description() for k, v in
                                                                   self.terrain.items()}
        self.tiles_age: Dict[Coords, int] = {}
        self.champions: Dict[
            ChampionDescription, Coords] = {}

        self.effect_weight: int = FIELD_ATTACKED
        self.can_hit: bool = False
        x_size, y_size = self.size
        self.terrain_matrix = [[FIELD_WEIGHT for _ in range(y_size)] for _ in range(x_size)]
        for position, tile in self.terrain.items():
            y, x = position  # to work it have to be swapped, don't know why
            if not tile.terrain_passable():
                self.terrain_matrix[x][y] = 0

        self.matrix = self.terrain_matrix.copy()

        self.weapons_destination_map = {}

    def register_effect(self, _, coords: Coords) -> None:
        y, x = coords
        self.matrix[x][y] = self.effect_weight

    def get_next_field(self) -> Coords:
        return self.position + self.champion.facing.value

    def get_left_field(self) -> Coords:
        return self.position + self.champion.facing.turn_left().value

    def get_right_field(self) -> Coords:
        return self.position + self.champion.facing.turn_right().value

    def increase_mist(self) -> None:
        self.mist_radius -= 1 if self.mist_radius > 0 else self.mist_radius
        if self.mist_radius:
            for coords in self.terrain:
                distance = points_dist(coords, self.menhir_position)
                y, x = coords
                if distance == self.mist_radius:
                    self.terrain_matrix[x][y] = FIELD_ATTACKED if self.terrain_matrix[x][y] else 0
                    self.terrain[coords].effects = True

    def prepare_matrix(self, knowledge: characters.ChampionKnowledge) -> None:

        if self.episode % MIST_TTH == 0:
            self.increase_mist()
        self.episode += 1

        self.prev_champion = self.champion
        self.champion = knowledge.visible_tiles.get(knowledge.position).character
        self.position = knowledge.position
        self.can_hit = False

        self.tiles_age = {**{k: v + 1 for k, v in self.tiles_age.items()},
                          **{k: 0 for k in knowledge.visible_tiles.keys()}}

        for position, tileDescription in knowledge.visible_tiles.items():
            if tileDescription.character and tileDescription.character != self.champion:
                self.champions[tileDescription.character] = position
            if tileDescription.loot:
                self.terrain_description[position] = tileDescription

        self.champions = {champ: cords for champ, cords in self.champions.items() if
                          not knowledge.visible_tiles.get(cords)
                          or knowledge.visible_tiles.get(cords).character == champ}

        self.matrix = copy.deepcopy(self.terrain_matrix)

        next_field = self.get_next_field()
        if self.matrix[next_field.y][next_field.x] > 0:
            self.matrix[next_field.y][next_field.x] /= 2

        used_weapon_importance = WEAPONS_ENCODING.get(self.champion.weapon)
        for position, tileDescription in self.terrain_description.items():
            y, x = position  # to work it have to be swapped, don't know why
            if tileDescription.loot:
                importance = WEAPONS_ENCODING.get(tileDescription.loot)
                if importance < used_weapon_importance:
                    self.matrix[x][y] = importance
                else:
                    self.matrix[x][y] *= importance

        for character, position in self.champions.items():
            age = self.tiles_age[position]
            y, x = position
            if age == 0:
                if WEAPONS_ENCODING.get(character.weapon) < used_weapon_importance:
                    self.matrix[x][y] = 1
                else:
                    self.matrix[x][y] = FIELD_ATTACKED
            else:
                self.matrix[x][y] += FIELD_ATTACKED / age

            aged_value = int(FIELD_ATTACKED / (age + 1))
            self.effect_weight = max(aged_value, FIELD_WEIGHT)
            weapon = WEAPONS_MAP.get(character.weapon)
            weapon.cut(self, position, character.facing)
            # todo add weight to potencially attacked fields
            # self.effect_weight = max(aged_value / 2, FIELD_WEIGHT)
            # weapon.cut(self, position, character.facing.turn_left())

        seen_champs = self.champions.values()

        def check_if_hit(_, coords: Coords) -> None:
            if coords in seen_champs:
                self.can_hit = True

        tmp = self.register_effect
        self.register_effect = check_if_hit
        weapon = WEAPONS_MAP.get(self.champion.weapon)
        weapon.cut(self, self.position, self.champion.facing)
        self.register_effect = tmp

        self.move_to_menhir = self.find_move_to_menhir()

    def find_move_to(self, end_position: Coords) -> DestinationWrapper:
        time = 0
        if end_position == self.position:
            return DestinationWrapper(end_position, time=time)
        if self.terrain[end_position].effects:
            return DestinationWrapper(end_position, time=-1)
        grid = Grid(matrix=self.matrix)
        start = grid.node(*self.position)
        end = grid.node(*end_position)
        path, _ = finder.find_path(start, end, grid)
        # print(grid.grid_str(path=path, start=start, end=end))
        if len(path) <= 0:
            return DestinationWrapper(end_position)
        else:
            action = Action.DO_NOTHING
            if self.get_next_field() == path[1]:
                action = Action.STEP_FORWARD
                time += 1
            elif self.get_right_field() == path[1]:
                action = Action.TURN_RIGHT
                time += 2
            elif self.get_left_field() == path[1]:
                action = Action.TURN_LEFT
                time += 2
            else:
                action = Action.TURN_LEFT
                time += 3
            if len(path) > 2:
                for idx, field in enumerate(path[2:]):
                    prev_field = path[idx]  # cords of field 2 turns ago
                    if prev_field[0] != field[0] and prev_field[1] != field[1]:  # it means that turning is needed
                        time += 2
                    else:
                        time += 1
            return DestinationWrapper(end_position, action, time)

    def find_best_move(self, coords: List[Coords]) -> DestinationWrapper:
        potential_actions = [self.find_move_to(position) for position in coords]
        return min(potential_actions, default=DestinationWrapper(None))

    def find_move_to_menhir(self) -> DestinationWrapper:
        if not self.menhir_destination or not self.move_to_menhir.reachable:
            # todo check nearest spot when path is blocked
            menhir_positions = [self.menhir_position + possible_postion.value for possible_postion in Facing]
            menhir_positions = [(len(self.check_position_surrounding(cord)), cord) for cord in menhir_positions if
                                self.terrain[cord].terrain_passable()]
            menhir_positions.sort()
            values = set(map(lambda x: x[0], menhir_positions))
            menhir_positions_grouped_by_value = [[y[1] for y in menhir_positions if y[0] == x] for x in values]
            for menhir_positions_grouped in menhir_positions_grouped_by_value:
                menhir_positions_grouped = [self.find_move_to(postion) for postion in menhir_positions_grouped]
                menhir_positions_grouped.sort()
                for potential_destination in menhir_positions_grouped:
                    if potential_destination.reachable:
                        self.menhir_destination = potential_destination.destination
                        return potential_destination
        return self.find_move_to(self.menhir_destination)

    def find_move_to_nearest_weapon(self, weapon: WeaponDescription) -> DestinationWrapper:
        weapon_destination = self.weapons_destination_map.get(weapon)
        if weapon_destination and self.terrain_description[weapon_destination].loot == weapon:
            action_wrapper = self.find_move_to(weapon_destination)
            if action_wrapper.reachable:
                return action_wrapper

        weapon_positions = [position for position, tileDescription in self.terrain_description.items() if
                            tileDescription.loot == weapon]
        best_action = self.find_best_move(weapon_positions)
        if best_action.reachable:
            self.weapons_destination_map[weapon] = best_action.destination
        if best_action.time == 0:
            return DestinationWrapper(best_action.destination, action=Action.STEP_FORWARD, time=4)
        return best_action

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

    def is_field_safe(self, coord: Coords, facing: Coords) -> bool:
        safe = True
        x, y = self.size
        while safe:
            coord += facing
            if coord[0] < 0 or coord[1] < 0 or coord[0] >= x or coord[1] >= y:
                break
            if self.terrain[coord].effects:
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
        surrounding = self.check_position_surrounding(self.position)
        direct_surrounding = [cord.value + self.position for cord in Facing]
        surrounding = [(self.tiles_age.get(cords, 0), cords) for cords in surrounding if cords in direct_surrounding]
        surrounding.sort(reverse=True)
        surrounding = [x[1] for x in surrounding]
        if len(surrounding) == 1:
            if self.position + self.champion.facing.value not in surrounding:
                return Action.TURN_LEFT
            return Action.DO_NOTHING
        if self.get_right_field() == surrounding[0]:
            return Action.TURN_RIGHT
        if self.get_left_field() == surrounding[0]:
            return Action.TURN_LEFT
        if self.get_right_field() == surrounding[1]:
            return Action.TURN_RIGHT
        if self.get_left_field() == surrounding[1]:
            return Action.TURN_LEFT
        return Action.TURN_LEFT

    def calc_mist_dist(self):
        return self.mist_radius - points_dist(self.position, self.menhir_position)
