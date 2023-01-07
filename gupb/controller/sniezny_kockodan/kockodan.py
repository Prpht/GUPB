import math
import random


from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import weapons
from gupb.model import coordinates
from gupb.model import tiles
from pathfinding.core.grid import Grid
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
from gupb.model.arenas import Arena

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK
]

WEAPON_DICT = {
    'knife': weapons.Knife,
    'sword': weapons.Sword,
    'bow': weapons.Bow,
    'axe': weapons.Axe,
    'amulet': weapons.Amulet
}

WEAPON_RANKING = {
    'knife': 1,
    'amulet': 2,
    'sword': 3,
    'bow': 4,
    'axe': 5
}

MAX_HEALTH: int = characters.CHAMPION_STARTING_HP
HEALTH_ATTACK_THRESHOLD: float = 1 / 3

MAX_WEAPON_PATH_LEN: int = 10

MENHIR_MOVEMENT_COUNTER_INIT: int = 50
CHAMPIONS_COUNT: int = 13

EUCLIDEAN_MAX_RADIUS: int = 7
EUCLIDEAN_MAX_RADIUS_ESC: int = 2

ESCAPE_MAX_COUNT: int = 2


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class SnieznyKockodanController(controller.Controller):
    weapon_distance = 5

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.menhir: (coordinates.Coords, None) = None
        self.mist: bool = False
        self.weapon_got: bool = False
        self.mist_destination: (coordinates.Coords, None) = None
        self.prev_position: (coordinates.Coords, None) = None
        self.prev_facing: (characters.Facing, None) = None
        self.attacked: bool = False
        self.menhir_attack_counter: int = 0
        self.memory_map: dict[coordinates.Coords, tiles.TileDescription] = {}
        self.random_walk_destination: (coordinates.Coords, None) = None
        # self.arcade_weapon: bool = True
        self.menhir_movement_counter: int = MENHIR_MOVEMENT_COUNTER_INIT
        self.prev_champions: int = CHAMPIONS_COUNT
        self.escape_destination: (coordinates.Coords, None) = None
        self.escape_counter: int = 0
        # self.arcade_weapon: bool = True
        self.map = None
        self.arena: (list[list[int]], None) = None
        self.terrain: dict[coordinates.Coords, tiles.TileDescription] = {}

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SnieznyKockodanController):
            return self.first_name == other.first_name

        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def _create_arena_matrix(self):
        arena = [[0 for _ in range(self.map.size[0])] for _ in range(self.map.size[1])]
        for cords, tile in self.terrain.items():
            arena[cords.y][cords.x] = 1 if tile.description().type in ["land", "menhir"] else 0
        return arena

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.decrement_menhir_movement_counter(knowledge)
            tiles_in_radius_esc = self.tiles_in_max_radius_esc(knowledge)
            if knowledge.position == self.random_walk_destination:
                self.random_walk_destination = None

            for tile in knowledge.visible_tiles:
                self.memory_map[tile] = knowledge.visible_tiles[tile]

            if self.need_to_randomize(knowledge):
                self.prev_position = knowledge.position
                self.prev_facing = knowledge.visible_tiles[knowledge.position].character.facing
                return self.random_decision()

            self.prev_position = knowledge.position
            self.prev_facing = knowledge.visible_tiles[knowledge.position].character.facing

            if self.escape_destination is not None:
                escape_destination = self.escape_destination
                self.escape_counter -= 1
                if self.escape_counter == 0:
                    self.escape_destination = None
                return self._move(knowledge, escape_destination)

            champion_info = knowledge.visible_tiles[knowledge.position].character

            weapon_to_get = self.find_weapon_to_get(knowledge)
            enemies_seen = SnieznyKockodanController.find_enemies_seen(knowledge)
            enemy_nearer_to_weapon = True
            mist_seen = SnieznyKockodanController.find_mist(knowledge)
            if len(mist_seen) > 0:
                self.mist = True

            if weapon_to_get is not None:  # and not self.arcade_weapon:
                enemy_nearer_to_weapon = SnieznyKockodanController.is_enemy_nearer_to_weapon(enemies_seen,
                                                                                             weapon_to_get,
                                                                                             knowledge.position)
            facing = champion_info.facing
            attack_eligible = self.is_eligible_to_attack(enemies_seen, facing, knowledge, champion_info)
            if self.menhir is None:
                self.menhir = SnieznyKockodanController.find_menhir(knowledge)

            if knowledge.position == self.menhir:
                if attack_eligible and self.menhir_attack_counter < 3:
                    self.menhir_attack_counter += 1
                    return self.attack()

                self.menhir_attack_counter = 0
                return self.random_decision(more_move=True)

            start_conditions = self.menhir_movement_counter >= MENHIR_MOVEMENT_COUNTER_INIT - 4

            if self.mist:
                if self.menhir is not None:
                    return self._move(knowledge, self.menhir)
                else:
                    return self.move_against_mist(mist_seen, knowledge)
            elif weapon_to_get is not None and not enemy_nearer_to_weapon and not start_conditions:
                return self._move(knowledge, weapon_to_get)
            elif attack_eligible and not start_conditions:
                return self.attack()
            elif self.need_to_escape(enemies_seen, tiles_in_radius_esc)[0] and not start_conditions:
                return self.escape(enemies_seen, knowledge)
            elif self.random_walk_destination is not None:
                return self._move(knowledge, self.random_walk_destination)
            elif not self.menhir_eligible():
                return self.walk_random_known(knowledge)
            elif self.menhir is not None and self.menhir_eligible():
                return self._move(knowledge, self.menhir)
            else:
                return self.walk_random_known(knowledge)
        except:
            return self.random_decision()

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir = None
        self.mist = False
        self.weapon_got = False
        self.mist_destination = None
        self.prev_position = None
        self.prev_facing = None
        self.attacked = False
        self.menhir_attack_counter = 0
        self.memory_map = {}
        self.terrain: dict[coordinates.Coords, tiles.TileDescription] = {}
        self.random_walk_destination = None
        self.menhir_movement_counter = MENHIR_MOVEMENT_COUNTER_INIT
        self.prev_champions = CHAMPIONS_COUNT
        self.escape_destination: (coordinates.Coords, None) = None
        self.escape_counter: int = 0
        self.map = Arena.load(arena_description.name)
        self.terrain = self.map.terrain
        self.arena = self._create_arena_matrix()

    @property
    def name(self) -> str:
        return f'MemeController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREY

    @staticmethod
    def count_x_distance(tile_position: coordinates.Coords, current_position: coordinates.Coords) -> int:
        return abs(tile_position[0] - current_position[0])

    @staticmethod
    def count_x_difference(tile_position: coordinates.Coords, current_position: coordinates.Coords) -> int:
        return tile_position[0] - current_position[0]

    @staticmethod
    def count_y_distance(tile_position: coordinates.Coords, current_position: coordinates.Coords) -> int:
        return abs(tile_position[1] - current_position[1])

    @staticmethod
    def count_y_difference(tile_position: coordinates.Coords, current_position: coordinates.Coords) -> int:
        return tile_position[1] - current_position[1]

    @staticmethod
    def is_potential_weapon_tile(tile_position: coordinates.Coords, current_position: coordinates.Coords) -> bool:
        x_distance = SnieznyKockodanController.count_x_distance(tile_position, current_position)
        if x_distance > SnieznyKockodanController.weapon_distance:
            y_distance = SnieznyKockodanController.count_y_distance(tile_position, current_position)
            return y_distance <= SnieznyKockodanController.weapon_distance

        return False

    @staticmethod
    def get_visible_weapons(knowledge: characters.ChampionKnowledge) -> list[coordinates.Coords]:
        visible_weapons = []
        for tile in knowledge.visible_tiles:
            if knowledge.visible_tiles[tile].loot is not None:
                visible_weapons += [tile]

        return visible_weapons

    @staticmethod
    def find_enemies_seen(knowledge: characters.ChampionKnowledge) -> list[coordinates.Coords]:
        enemies = []
        for tile in knowledge.visible_tiles:
            if knowledge.visible_tiles[tile].character is not None and tile != knowledge.position:
                enemies += [tile]

        return enemies

    def find_enemies(self, knowledge: characters.ChampionKnowledge):
        enemies = []
        for tile in self.memory_map:
            if self.memory_map[tile].character is not None and tile != knowledge.position:
                enemies += [tile]

        return enemies

    @staticmethod
    def is_enemy_nearer_to_weapon(enemies: list[coordinates.Coords],
                                  weapon: coordinates.Coords,
                                  current_position: coordinates.Coords) -> bool:
        current_distance = min(
            SnieznyKockodanController.count_y_distance(weapon, current_position),
            SnieznyKockodanController.count_x_distance(weapon, current_position)
        )
        for enemy in enemies:
            enemy_distance = min(
                SnieznyKockodanController.count_y_distance(weapon, enemy),
                SnieznyKockodanController.count_x_distance(weapon, enemy)
            )
            if enemy_distance <= current_distance:
                return True

        return False

    def is_eligible_to_attack(self, enemies: list[coordinates.Coords],
                              facing: characters.Facing,
                              knowledge: characters.ChampionKnowledge,
                              champion_info: characters.ChampionDescription) -> bool:
        if len(self.terrain) == 0:
            return False

        # health = champion_info.health
        # enemy_stronger_health = [knowledge.visible_tiles[enemy].character.health > health for enemy in enemies]
        # if any(enemy_stronger_health):
        #     return False
        # if health < HEALTH_ATTACK_THRESHOLD * MAX_HEALTH:
        #     return False

        weapon = champion_info.weapon.name
        # enemy_stronger_weapons = [WEAPON_RANKING[knowledge.visible_tiles[enemy].character.weapon.name]
        #                           > WEAPON_RANKING[weapon]
        #                           for enemy in enemies]
        # if any(enemy_stronger_weapons):
        #     return False
        try:
            weapon_coordinates = WEAPON_DICT[weapon].cut_positions(self.terrain, knowledge.position, facing)
        except TypeError:
            weapon_coordinates = []

        for enemy in enemies:  # self.find_enemies(knowledge):
            if enemy in weapon_coordinates:
                return True

        return False

    def find_weapon_to_get(self, knowledge: characters.ChampionKnowledge) -> (coordinates.Coords, None):
        if not self.weapon_got:
            visible_weapons = SnieznyKockodanController.get_visible_weapons(knowledge)
            for weapon in visible_weapons:
                if SnieznyKockodanController.is_potential_weapon_tile(weapon, knowledge.position):
                    return weapon

            return None

        return None

    @staticmethod
    def find_mist(knowledge: characters.ChampionKnowledge) -> list[coordinates.Coords]:
        mist_tiles = []
        for tile in knowledge.visible_tiles:
            effects_on_tile = knowledge.visible_tiles[tile].effects
            for effect in effects_on_tile:
                if effect.type == 'mist':
                    mist_tiles += [tile]
        return mist_tiles

    @staticmethod
    def find_menhir(knowledge: characters.ChampionKnowledge) -> (coordinates.Coords, None):
        for tile in knowledge.visible_tiles:
            if knowledge.visible_tiles[tile].type == 'menhir':
                return tile
        return None

    def move_against_mist(self,
                          mist_tiles: list[coordinates.Coords],
                          knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.attacked = False
        if len(mist_tiles) == 0:
            return self._move(knowledge, self.mist_destination)

        euclidean_distances = [SnieznyKockodanController.euclidean_distance(knowledge.position, x) for x in mist_tiles]
        min_tile_ind = euclidean_distances.index(min(euclidean_distances))

        neighbourhood = self.find_eligible_tiles_in_neighbourhood(knowledge)
        euclidean_neighbourhood = [SnieznyKockodanController.euclidean_distance(mist_tiles[min_tile_ind], tile)
                                   for tile in neighbourhood]
        max_neigh_ind = euclidean_neighbourhood.index(max(euclidean_neighbourhood))
        destination = neighbourhood[max_neigh_ind]
        self.mist_destination = destination
        return self._move(knowledge, destination)

    def find_path(self, start: coordinates.Coords, destination: coordinates.Coords) -> list[coordinates.Coords]:
        grid = Grid(matrix=self.arena)
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        start = grid.node(start.x, start.y)
        destination = grid.node(destination[0], destination[1])
        path, _ = finder.find_path(start, destination, grid)
        return path[1:]

    def _move(self,
              champion_knowledge: characters.ChampionKnowledge,
              destination_coordinates: coordinates.Coords) -> characters.Action:
        self.attacked = False
        current_coordinates = champion_knowledge.position
        current_facing = champion_knowledge.visible_tiles.get(champion_knowledge.position).character.facing

        path = self.find_path(current_coordinates, destination_coordinates)
        if current_coordinates + current_facing.value == path[0]:
            return characters.Action.STEP_FORWARD

        if current_coordinates + current_facing.turn_right().value == path[0]:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_LEFT

    @staticmethod
    def get_map_center(terrain: arenas.Terrain) -> coordinates.Coords:
        size = arenas.terrain_size(terrain)
        return coordinates.Coords(x=math.ceil(size[0] / 2) - 1,
                                  y=math.ceil(size[1] / 2) - 1)

    def attack(self) -> characters.Action:
        self.attacked = True
        return characters.Action.ATTACK

    def random_decision(self, more_move=False) -> characters.Action:
        if more_move:
            action = random.choice(POSSIBLE_ACTIONS + [characters.Action.STEP_FORWARD])
        else:
            action = random.choice(POSSIBLE_ACTIONS)

        self.attacked = action == characters.Action.ATTACK
        return action

    def need_to_randomize(self, knowledge: characters.ChampionKnowledge) -> bool:
        return self.prev_position == knowledge.position \
               and self.prev_facing == knowledge.visible_tiles[knowledge.position].character.facing \
               and not self.attacked

    # def arcade_weapon_gain(self, current_position):
    #     corners: dict[coordinates.Coords, int] = {
    #         coordinates.Coords(1, 1): 1000,
    #         coordinates.Coords(1, ARENA.size[1] - 2): 1000,
    #         coordinates.Coords(ARENA.size[0] - 2, 1): 1000,
    #         coordinates.Coords(ARENA.size[0] - 2, ARENA.size[1] - 2): 1000
    #     }
    #
    #     for corner in corners:
    #         corners[corner] = len(self.find_path(current_position, corner))
    #
    #     nearest_corner = min(corners, key=corners.get)
    #     if corners[nearest_corner] > MAX_WEAPON_PATH_LEN:
    #         self.arcade_weapon = False
    #
    #     return nearest_corner

    def menhir_eligible(self) -> bool:
        return self.menhir_movement_counter < 0

    def decrement_menhir_movement_counter(self, knowledge: characters.ChampionKnowledge) -> None:
        self.menhir_movement_counter -= 1
        self.menhir_movement_counter -= self.prev_champions - knowledge.no_of_champions_alive
        self.prev_champions = knowledge.no_of_champions_alive

    def walk_random_known(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        available_spots = self.find_eligible_tiles_in_neighbourhood(knowledge)
        destination = random.choice(available_spots)
        self.random_walk_destination = coordinates.Coords(destination[0], destination[1])
        return self._move(knowledge, destination)

    def find_eligible_tiles_in_neighbourhood(self, knowledge: characters.ChampionKnowledge):
        exploration_probability = 0.4
        current_position = knowledge.position
        spots = []
        for x in range(self.map.size[0]):
            for y in range(self.map.size[1]):
                if self.arena[y][x] == 1:
                    spots.append((x, y))
        eligible_spots = []
        eligible_spots_not_in_neighbourhood = []
        for spot in spots:
            destination = coordinates.Coords(spot[0], spot[1])
            distance = self.euclidean_distance(current_position, destination)
            path = self.find_path(current_position, destination)
            if destination != current_position and path:
                if distance <= EUCLIDEAN_MAX_RADIUS:
                    eligible_spots.append(spot)
                else:
                    eligible_spots_not_in_neighbourhood.append(spot)

        return eligible_spots if random.random() > exploration_probability else eligible_spots_not_in_neighbourhood

    @staticmethod
    def euclidean_distance(position1: coordinates.Coords, position2: coordinates.Coords) -> float:
        return math.sqrt((position1.x - position2.x) ** 2 + (position2.y - position1.y) ** 2)

    # def tiles_in_max_radius(self, knowledge: characters.ChampionKnowledge) -> list[coordinates.Coords]:
    #     positions_in_radius = []
    #     for tile in self.memory_map:
    #         if SnieznyKockodanController.euclidean_distance(coordinates.Coords(tile[0], tile[1]),
    #                                                         knowledge.position) <= EUCLIDEAN_MAX_RADIUS:
    #             positions_in_radius += [coordinates.Coords(tile[0], tile[1])]
    #
    #     return positions_in_radius

    def tiles_in_max_radius_esc(self, knowledge: characters.ChampionKnowledge) -> list[coordinates.Coords]:
        positions_in_radius = []
        for tile in self.memory_map:
            if SnieznyKockodanController.euclidean_distance(coordinates.Coords(tile[0], tile[1]),
                                                            knowledge.position) <= EUCLIDEAN_MAX_RADIUS_ESC:
                positions_in_radius += [coordinates.Coords(tile[0], tile[1])]

        return positions_in_radius

    def need_to_escape(self, enemies: list[coordinates.Coords], tiles_in_radius: list[coordinates.Coords]) \
            -> (bool, (coordinates.Coords, None)):
        for enemy in enemies:
            if enemy in tiles_in_radius:
                return True, enemy

        return False, None

    def escape(self, enemies: list[coordinates.Coords],
               knowledge: characters.ChampionKnowledge) -> characters.Action:
        euclidean_distances = [
            SnieznyKockodanController.euclidean_distance(knowledge.position, coordinates.Coords(enemy[0], enemy[1]))
            for enemy in enemies]
        min_tile_ind = euclidean_distances.index(min(euclidean_distances))
        neighbourhood = self.find_eligible_tiles_in_neighbourhood(knowledge)
        euclidean_neighbourhood = [SnieznyKockodanController.euclidean_distance(
            coordinates.Coords(enemies[min_tile_ind][0], enemies[min_tile_ind][1]),
            coordinates.Coords(tile[0], tile[1]))
            for tile in neighbourhood]
        max_neigh_ind = euclidean_neighbourhood.index(max(euclidean_neighbourhood))
        self.escape_destination = coordinates.Coords(neighbourhood[max_neigh_ind][0], neighbourhood[max_neigh_ind][1])
        self.escape_counter = ESCAPE_MAX_COUNT
        return self._move(knowledge, self.escape_destination)
