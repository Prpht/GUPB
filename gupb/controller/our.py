import random
from typing import Dict, Tuple, Optional, List, NamedTuple

from pathfinding.core.grid import Grid
from pathfinding.core.node import GridNode
from pathfinding.finder.a_star import AStarFinder

from gupb import controller
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.coordinates import Coords

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

MAX_SIZE = 20


class SeenWeapon(NamedTuple):
    name: str
    seen_epoch_nr: int


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class OurController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.current_position: Optional[coordinates.Coords] = None
        # remembering map
        self.epoch: int = 0
        self.seen_tiles: Dict[coordinates.Coords, Tuple[tiles.TileDescription, int]] = {}

        # pathfinding
        self.grid: Optional[Grid] = None
        self.maps: Dict[str]

        self.menhir_coords: Optional[coordinates.Coords] = None
        self.wapons_coords: Dict[coordinates.Coords, SeenWeapon] = {}
        self.finder: Optional[AStarFinder] = None
        self.paths = {
            'to_menhir': None,
            'to_nearest_weapon': None
        }
        self.actions_iterator = 0
        self.actions = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OurController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        for coords, tile in knowledge.visible_tiles.items():
            print("c", coords)
        try:
            self.update_state(knowledge)

            x, y = self.current_position
            path = self.finder.find_path(self.grid.node(x, y), self.grid.node(6, 4), self.grid)
            if not self.actions:
                self.actions = self.map_path_to_action_list(knowledge.position, path[0])

            if self.actions and self.actions_iterator < len(self.actions):
                action = self.actions[self.actions_iterator]
                self.actions_iterator += 1
            else:
                action = random.choice(POSSIBLE_ACTIONS) #TODO add tab
            print(self.actions)
        except Exception as e:
            print(e)
        return action

    # naliczyć najkrótsze ścieżki po aktualizacji mapy oraz po dotarciu do punktu
    # dict z najkrótszymi ścieżkami.
    def update_state(self, knowledge: characters.ChampionKnowledge):
        self.current_position = knowledge.position
        self.seen_tiles.update(dict((x[0], (x[1], self.epoch)) for x in knowledge.visible_tiles.items()))
        self.epoch += 1
        self.build_grid()
        self.finder = AStarFinder()
        self.look_up_for_menhir(knowledge.visible_tiles)
        self.look_up_for_weapons(knowledge.visible_tiles)

    def map_path_to_action_list(self, current_position: Coords, path: List[GridNode]) -> List[characters.Action]:
        initial_facing = self.seen_tiles[current_position][0].character.facing
        facings: List[characters.Facing] = list(
            map(lambda a: characters.Facing(Coords(a[1].x - a[0].x, a[1].y - a[0].y)), list(zip(path[:-1], path[1:]))))
        actions: List[characters.Action] = []
        for a, b in zip([initial_facing, *facings[:-1]], facings):
            actions.extend(self.map_facings_to_actions(a, b))
        return actions

    def xxmap_facings_to_actions(self, f1: characters.Facing, f2: characters.Facing) -> List[characters.Action]:
        if f1 == f2:
            return [characters.Action.STEP_FORWARD]
        elif f1.turn_left() == f2:
            return [characters.Action.TURN_LEFT, characters.Action.STEP_FORWARD]
        elif f1.turn_right() == f2:
            return [characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]
        else:
            return [characters.Action.TURN_RIGHT, characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        print(
            arena_description)  # dostajemy to także przed pierwszą turą - możemy zapamiętywać mapy między rozgrywkami po ich nazwie
        # reset roud unique variables
        self.epoch = 0
        self.actions = []
        self.actions_iterator = 0
        self.seen_tiles = {}

    def build_grid(self):
        def extract_walkable_tiles():
            return list(filter(lambda x: x[1][0].type == 'land', self.seen_tiles.items()))

        walkable_tiles_list = extract_walkable_tiles()
        walkable_tiles_matrix = [[0 for y in range(MAX_SIZE)] for x in range(MAX_SIZE)]

        for tile in walkable_tiles_list:
            x, y = tile[0]
            walkable_tiles_matrix[y][x] = 1
        try:
            self.grid = Grid(MAX_SIZE, MAX_SIZE, walkable_tiles_matrix)
        except Exception as e:
            print(e)

    def look_up_for_menhir(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        if not self.menhir_coords:
            for coords, tile in tiles.items():
                if tile.type == 'menhir':
                    self.menhir_coords = coords
                    break

    def look_up_for_weapons(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, tile in tiles.items():
            if self.wapons_coords[coords]:
                self._update_waepon(coords, tile)
            if tile.loot:
                self._add_weapon(coords, tile)

    def _add_weapon(self, coords, tile):
        self.wapons_coords[coords] = SeenWeapon(tile.loot.name, self.epoch)

    def _update_waepon(self, coords, tile):
        if not tile.loot:
            del self.wapons_coords[coords]

    def find_mist(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> List[coordinates.Coords]:
        mist_coords = []
        for coords, tile in tiles.items():
            for effect in tile.effects:
                if effect.type == 'fog':
                    mist_coords.append(coords)
        return mist_coords

    def find_nearest_mist_coords(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> Optional[coordinates.Coords]:
        mist_coords = self.find_mist(tiles)
        if mist_coords:
            nearest_mist_coords = self.find_nearest_coords(self.current_position, mist_coords)
            return nearest_mist_coords
        else:
            return None

    def find_nearest_enemy_coords(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> Optional[coordinates.Coords]:
        enemies_coords = self.find_enemies_coords(tiles)
        if enemies_coords:
            nearest_enemy_coords = self.find_nearest_coords(self.current_position, enemies_coords)
            return nearest_enemy_coords
        else:
            return None

    def find_enemies_coords(self, tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> List[coordinates.Coords]:
        enemies_coords = []
        for coords, tile in tiles.items():
            if tile.character:
                enemies_coords.append(coords)
        return enemies_coords

    def find_nearest_coords(self, point_coords: coordinates.Coords, coords: List[coordinates.Coords]) -> Optional[coordinates.Coords]:
        min_distance_squared = 2 * MAX_SIZE ** 2
        nearest_coords = None
        for coords in coords:
            distance_squared = self.calc_distance(point_coords, coords)
            if distance_squared < min_distance_squared:
                min_distance_squared = distance_squared
                nearest_coords = coords
        return nearest_coords

    def calc_distance(self, coords_1: coordinates.Coords, coords_2: coordinates.Coords) -> int:
        return (coords_1.x - coords_2.x) ** 2 + (coords_1.y - coords_2.y) ** 2
    @property
    def name(self) -> str:
        return f'OurController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    OurController("OOOOR"),
]
