import random
from typing import Dict, Tuple, Optional, List, NamedTuple, NewType

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

SeenTileT = NewType("SeenTileT", Tuple[tiles.TileDescription, int])
SeenTilesT = NewType("SeenTilesT", Dict[coordinates.Coords, SeenTileT])
CoordsListT = NewType("CoordsListT", List[coordinates.Coords])
TilesT = NewType("TilesT", Dict[coordinates.Coords, tiles.TileDescription])


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
        self.seen_tiles: SeenTilesT = {}

        # pathfinding
        self.grid: Optional[Grid] = None
        self.maps: Dict[str]

        self.menhir_coords: Optional[coordinates.Coords] = None
        self.weapons_coords: Dict[coordinates.Coords, SeenWeapon] = {}
        self.finder: Optional[AStarFinder] = None
        self.paths = {
            'to_menhir': None,
            'to_nearest_weapon': None
        }
        self.actions_iterator = 0
        self.actions = []
        self.current_map_name = None
        self.maps: Dict[str, SeenTilesT] = {}

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OurController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
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
        print("PRAISE")
        self.remember_map()
        print(self.maps)
        print("PRAISE END")

    def remember_map(self):
        self.reset_seen_tiles()
        if self.current_map_name in self.maps.keys():
            self.maps[self.current_map_name].update(self.seen_tiles)
        else:
            self.maps[self.current_map_name] = self.seen_tiles

    def reset_seen_tiles(self):
        for coords, tile_round in self.seen_tiles.items():
            self.seen_tiles[coords] = self.get_reset_seen_tile(tile_round)

    def get_reset_seen_tile(self, tile: SeenTileT) -> SeenTileT:
        epoch = 0
        tile = tiles.TileDescription(tile[0].type, tile[0].loot, None, None, [])  # todo czy nietrzeba usunąć czegoś co się zmienia?
        return tile, epoch

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        print(
            arena_description)
        # reset roud unique variables
        self.current_map_name = arena_description.name
        self.epoch = 0
        self.actions = []
        self.actions_iterator = 0
        self.seen_tiles = self.maps.get(arena_description.name, dict())
        print("INIT MAP:", arena_description.name, self.seen_tiles)

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

    def look_up_for_menhir(self, tiles: TilesT):
        if not self.menhir_coords:
            for coords, tile in tiles.items():
                if tile.type == 'menhir':
                    self.menhir_coords = coords
                    break

    def look_up_for_weapons(self, tiles: TilesT):
        for coords, tile in tiles.items():
            if self.weapons_coords[coords]:
                self._update_waepon(coords, tile)
            if tile.loot:
                self._add_weapon(coords, tile)

    def _add_weapon(self, coords, tile):
        self.weapons_coords[coords] = SeenWeapon(tile.loot.name, self.epoch)

    def _update_waepon(self, coords, tile):
        if not tile.loot:
            del self.weapons_coords[coords]

    def find_mist(self, tiles: TilesT) -> CoordsListT:
        mist_coords = []
        for coords, tile in tiles.items():
            for effect in tile.effects:
                if effect.type == 'fog':
                    mist_coords.append(coords)
        return mist_coords

    def find_nearest_mist_coords(self, tiles: TilesT) -> Optional[coordinates.Coords]:
        mist_coords = self.find_mist(tiles)
        if mist_coords:
            nearest_mist_coords = self.find_nearest_coords(self.current_position, mist_coords)
            return nearest_mist_coords
        else:
            return None

    def find_nearest_enemy_coords(self, tiles: TilesT) -> Optional[coordinates.Coords]:
        enemies_coords = self.find_enemies_coords(tiles)
        if enemies_coords:
            nearest_enemy_coords = self.find_nearest_coords(self.current_position, enemies_coords)
            return nearest_enemy_coords
        else:
            return None

    def find_enemies_coords(self, tiles: TilesT) -> CoordsListT:
        enemies_coords = []
        for coords, tile in tiles.items():
            if tile.character:
                enemies_coords.append(coords)
        return enemies_coords

    def find_nearest_coords(self, point_coords: coordinates.Coords, coords: CoordsListT) -> Optional[coordinates.Coords]:
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
