import math
import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import weapons
from gupb.model import effects
from gupb.model import coordinates
from queue import SimpleQueue
from pathfinding.core.grid import Grid
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder

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

TERRAIN_NAME = 'lone_sanctum'

ARENA = arenas.Arena.load(TERRAIN_NAME)
TERRAIN = ARENA.terrain

MAX_HEALTH: int = characters.CHAMPION_STARTING_HP
HEALTH_ATTACK_THRESHOLD: float = 1/3


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class SnieznyKockodanController(controller.Controller):
    weapon_distance = 5

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.menhir: (coordinates.Coords, None) = None
        self.mist: bool = False
        #self.move_queue: SimpleQueue[characters.Action] = SimpleQueue()
        self.weapon_got: bool = False
        self.mist_destination: (coordinates.Coords, None) = None
        self.arena = self._create_arena_matrix()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SnieznyKockodanController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def _create_arena_matrix(self):
        arena = [[0 for _ in range(ARENA.size[0])] for _ in range(ARENA.size[1])]
        for cords, tile in TERRAIN.items():
            arena[cords.y][cords.x] = 1 if tile.description().type == 'land' else 0
        return arena

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        champion_info = knowledge.visible_tiles[knowledge.position].character
        weapon_to_get = self.find_weapon_to_get(knowledge)
        enemies_seen = SnieznyKockodanController.find_enemies_seen(knowledge)
        enemy_nearer_to_weapon = True
        mist_seen = SnieznyKockodanController.find_mist(knowledge)
        if len(mist_seen) > 0:
            self.mist = True
        if weapon_to_get is not None:
            enemy_nearer_to_weapon = SnieznyKockodanController.is_enemy_nearer_to_weapon(enemies_seen, weapon_to_get,
                                                                                         knowledge.position)
        facing = champion_info.facing
        attack_eligible = self.is_eligible_to_attack(enemies_seen, facing, knowledge, champion_info)
        if self.menhir is None:
            self.menhir = SnieznyKockodanController.find_menhir(knowledge)

        if knowledge.position == self.menhir:
            return random.choice(POSSIBLE_ACTIONS)

        if self.mist:
            if self.menhir is not None:
                return self._move(knowledge, self.menhir)
            else:
                return self.move_against_mist(mist_seen, knowledge)
        elif weapon_to_get is not None and not enemy_nearer_to_weapon:
            return self._move(knowledge, weapon_to_get)
        elif attack_eligible:
            return characters.Action.ATTACK
        elif self.menhir is not None:
            return self._move(knowledge, self.menhir)
        else:
            return random.choice(POSSIBLE_ACTIONS)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir = None
        self.mist = False
        self.weapon_got = False
        self.mist_destination = None

    @property
    def name(self) -> str:
        return f'SnieznyKockodanController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE

    @staticmethod
    def count_x_distance(tile_position: coordinates.Coords, current_position: coordinates.Coords) -> int:
        return abs(tile_position[0] - current_position[0])

    @staticmethod
    def count_y_distance(tile_position: coordinates.Coords, current_position: coordinates.Coords) -> int:
        return abs(tile_position[1] - current_position[1])

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
            if knowledge.visible_tiles[tile].character is not None:
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
        health = champion_info.health
        # enemy_stronger_health = [knowledge.visible_tiles[enemy].character.health > health for enemy in enemies]
        # if any(enemy_stronger_health):
        #     return False
        if health < HEALTH_ATTACK_THRESHOLD * MAX_HEALTH:
            return False

        weapon = champion_info.weapon.name
        enemy_stronger_weapons = [WEAPON_RANKING[knowledge.visible_tiles[enemy].character.weapon.name]
                                  > WEAPON_RANKING[weapon]
                                  for enemy in enemies]
        if any(enemy_stronger_weapons):
            return False
        try:
            weapon_coordinates = WEAPON_DICT[weapon].cut_positions(TERRAIN, knowledge.position, facing)
        except TypeError:
            weapon_coordinates = []

        for enemy in enemies:
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
                if isinstance(effect, effects.Mist):
                    mist_tiles += [tile]
                    break

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
        if len(mist_tiles) == 0:
            return self._move(knowledge, self.mist_destination)

        x_distances = [SnieznyKockodanController.count_x_distance(mist_tile, knowledge.position)
                       for mist_tile in mist_tiles]
        y_distances = [SnieznyKockodanController.count_y_distance(mist_tile, knowledge.position)
                       for mist_tile in mist_tiles]

        x_ind = x_distances.index(min(x_distances))
        y_ind = y_distances.index(min(y_distances))

        destination = coordinates.Coords(x=knowledge.position[0], y=knowledge.position[1])
        difference = coordinates.sub_coords(coordinates.Coords(mist_tiles[x_ind].x, mist_tiles[y_ind].y), destination)
        destination = coordinates.sub_coords(destination, difference)
        self.mist_destination = destination
        return self._move(knowledge, destination)

    def find_path(self, start: coordinates.Coords, destination: coordinates.Coords):
        grid = Grid(matrix=self.arena)
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        start = grid.node(start.x, start.y)
        destination = grid.node(destination[0], destination[1])
        path, _ = finder.find_path(start, destination, grid)
        return path[1:]

    def _move(self,
              champion_knowledge: characters.ChampionKnowledge,
              destination_coordinates: coordinates.Coords) -> characters.Action:

        current_coordinates = champion_knowledge.position
        current_facing = champion_knowledge.visible_tiles.get(champion_knowledge.position).character.facing

        path = self.find_path(current_coordinates, destination_coordinates)

        if current_coordinates + current_facing.value == path[0]:
            return characters.Action.STEP_FORWARD

        if current_coordinates + current_facing.turn_right().value == path[0]:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_LEFT


    def get_map_center(self, terrain: arenas.Terrain) -> coordinates.Coords:
        size = arenas.terrain_size(terrain)
        return coordinates.Coords(x=math.ceil(size[0] / 2) - 1,
                                  y=math.ceil(size[1] / 2) - 1)
