from typing import Dict
from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.grid import Grid
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import ChampionDescription
from gupb.model.tiles import Menhir, Wall, Sea, Land
from gupb.model.weapons import Knife, Sword, Bow, Axe, Amulet

FIELD_WEIGHT = 100

TILES = [Land, Sea, Wall, Menhir]

TILES_MAP = {tile().description().type: tile for tile in TILES}

WEAPONS = [(Knife, 0), (Sword, FIELD_WEIGHT), (Bow, 1), (Axe, 5), (Amulet, 3)]

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

    def get_champion(self, knowledge: characters.ChampionKnowledge) -> ChampionDescription:
        return self.terrain.get(knowledge.position).character

    def find_next_move(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        x_size, y_size = self.size
        self.matrix = [[FIELD_WEIGHT for _ in range(y_size)] for _ in range(x_size)]
        champion = self.get_champion(knowledge)
        used_weapon = WEAPONS_ENCODING.get(champion.weapon)
        next_field = knowledge.position + champion.facing.value
        self.matrix[next_field[1]][next_field[0]] = FIELD_WEIGHT / 2

        for position, tileDescription in self.terrain.items():
            y, x = position
            if tileDescription.character and tileDescription.character != champion:
                self.matrix[x][y] = -1
                weapon = WEAPONS_MAP.get(tileDescription.character.weapon)
                weapon.cut(self, position, tileDescription.character.facing)
            elif self.matrix[x][y] > 0:
                if tileDescription.loot:
                    importance = WEAPONS_ENCODING.get(tileDescription.loot)
                    if importance > used_weapon:
                        self.matrix[x][y] = importance
                    else:
                        self.matrix[x][y] = -2
                else:
                    if not TILES_MAP.get(tileDescription.type).terrain_passable():
                        self.matrix[x][y] = 0
        grid = Grid(matrix=self.matrix)
        start = grid.node(*knowledge.position)
        end = grid.node(self.menhir_position[0], self.menhir_position[1] + 1)
        path, _ = finder.find_path(start, end, grid)
        print(grid.grid_str(path=path, start=start, end=end))
        print(path)
        print(knowledge.position)
        print(champion.facing.value)
        if len(path) > 1 and next_field == path[1]:
            return characters.Action.STEP_FORWARD
        else:
            return characters.Action.TURN_LEFT

    def register_effect(self, _, coords: coordinates.Coords) -> None:
        y, x = coords
        self.matrix[x][y] = -1


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

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        arena = arenas.Arena.load(arena_description.name)
        self.arena = ArenaMapped(arena)
        self.arena.menhir_position = arena_description.menhir_position

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.arena.terrain = {**self.arena.terrain, **knowledge.visible_tiles}
        # It's assumed that the whole map is known
        return self.arena.find_next_move(knowledge)

    @property
    def name(self) -> str:
        return f'ShallowMindController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREY


POTENTIAL_CONTROLLERS = [
    ShallowMindController('test'),
]
