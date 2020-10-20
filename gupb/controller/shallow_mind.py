import random

from typing import Dict

from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.grid import Grid

from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.arenas import Terrain, terrain_size, Arena
from gupb.model.characters import ChampionDescription
from gupb.model.tiles import Menhir, Wall, Sea, Land
from gupb.model.weapons import Knife, Sword, Bow, Axe, Amulet

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

FIELD_WEIGHT = 100

TILES = [Land, Sea, Wall, Menhir]

TILES_MAP = {tile().description().type: tile for tile in TILES}

WEAPONS = [(Knife, 0), (Sword, FIELD_WEIGHT), (Bow, 1), (Axe, 5), (Amulet, 3)]

WEAPONS_CLASSES = [x for x, _ in WEAPONS]

WEAPONS_MAP = {weapon().description(): weapon for weapon, _ in WEAPONS}

WEAPONS_ENCODING = {weapon().description(): value for weapon, value in WEAPONS}

finder = AStarFinder()


def terrain_transparent_monkey_patch(self) -> bool:
    return TILES_MAP[self.type].terrain_transparent()


def transparent_monkey_patch(self) -> bool:
    return self.terrain_transparent() and not self.character


tiles.TileDescription.terrain_transparent = terrain_transparent_monkey_patch
tiles.TileDescription.transparent = transparent_monkey_patch


class ArenaMapped(Arena):
    def __init__(self, arena):
        super().__init__(arena.name, arena.terrain)
        self.terrain: Dict[coordinates.Coords, tiles.TileDescription] = {k: v.description() for k, v in
                                                                         arena.terrain.items()}
        self.matrix = []

    def prepare_matrix(self) -> None:
        x_size, y_size = self.size
        self.matrix = [[FIELD_WEIGHT for _ in range(y_size)] for _ in range(x_size)]

    def register_effect(self, _, coords: coordinates.Coords) -> None:
        x, y = coords
        self.matrix[x][y] = -1


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class ShallowMindController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.prev_champion: ChampionDescription = None
        self.arena: ArenaMapped = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ShallowMindController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def __get_champion(self, knowledge: characters.ChampionKnowledge) -> ChampionDescription:
        return self.arena.terrain.get(knowledge.position).character

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        arena = arenas.Arena.load(arena_description.name)
        self.arena = ArenaMapped(arena)
        self.arena.menhir_position = arena_description.menhir_position

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        arena = self.arena
        arena.terrain = {**arena.terrain, **knowledge.visible_tiles}
        champ = self.__get_champion(knowledge)
        used_weapon = WEAPONS_ENCODING.get(champ.weapon)
        # It's assumed that the whole map is known
        self.arena.prepare_matrix()
        next_field = knowledge.position + champ.facing.value
        self.arena.matrix[next_field[1]][next_field[0]] = FIELD_WEIGHT / 2

        for position, tileDescription in arena.terrain.items():
            y, x = position
            if tileDescription.character:
                arena.matrix[x][y] = -1
                weapon = WEAPONS_MAP.get(tileDescription.character.weapon)
                weapon.cut(self.arena, position, tileDescription.character.facing)
            elif arena.matrix[x][y] > 0:
                if tileDescription.loot:
                    importance = WEAPONS_ENCODING.get(tileDescription.loot)
                    if importance > used_weapon:
                        arena.matrix[x][y] = importance
                    else:
                        arena.matrix[x][y] = -2
                else:
                    if not TILES_MAP.get(tileDescription.type).terrain_passable():
                        arena.matrix[x][y] = 0

        grid = Grid(matrix=self.arena.matrix)
        start = grid.node(*knowledge.position)
        end = grid.node(self.arena.menhir_position[0], self.arena.menhir_position[1]+1)
        path, runs = finder.find_path(start, end, grid)
        self.prev_champion = champ
        if len(path) > 1 and next_field == path[1]:
            return characters.Action.STEP_FORWARD
        else:
            return characters.Action.TURN_LEFT

    @property
    def name(self) -> str:
        return f'ShallowMindController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREY


POTENTIAL_CONTROLLERS = [
    ShallowMindController('test'),
]
