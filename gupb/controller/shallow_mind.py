from typing import Dict, Tuple
from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.grid import Grid
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import ChampionDescription, Facing
from gupb.model.games import MIST_TTH
from gupb.model.tiles import Menhir, Wall, Sea, Land
from gupb.model.weapons import Knife, Sword, Bow, Axe, Amulet
from queue import SimpleQueue

FIELD_WEIGHT = 100

TILES = [Land, Sea, Wall, Menhir]

TILES_MAP = {tile().description().type: tile for tile in TILES}

WEAPONS = [(Knife, 0), (Sword, FIELD_WEIGHT), (Bow, 1), (Axe, 5), (Amulet, 3)]

WEAPONS_MAP = {weapon().description(): weapon for weapon, _ in WEAPONS}

WEAPONS_ENCODING = {weapon().description(): value for weapon, value in WEAPONS}

finder = AStarFinder()

FIELD_ATTACKED = FIELD_WEIGHT * FIELD_WEIGHT * FIELD_WEIGHT


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
        self.tiles_memory: Dict[coordinates.Coords, tiles.TileDescription] = {}
        self.champions: Dict[ChampionDescription, Tuple[coordinates.Coords, int]] = {}
        self.matrix = []
        self.champion: ChampionDescription = None
        self.position: coordinates.Coords = None
        self.episode: int = 0
        self.effect_weight: int = FIELD_ATTACKED

    def get_next_field(self) -> coordinates.Coords:
        return self.position + self.champion.facing.value

    def get_left_field(self):
        return self.position + self.champion.facing.turn_left().value

    def get_right_field(self):
        return self.position + self.champion.facing.turn_right().value

    def prepare_matrix(self, knowledge: characters.ChampionKnowledge) -> None:
        self.champions = {champ: (tere[0], tere[1] + 1) for champ, tere in self.champions.items()}
        self.tiles_memory = {**self.tiles_memory, **knowledge.visible_tiles}
        self.champion = knowledge.visible_tiles.get(knowledge.position).character
        self.position = knowledge.position
        x_size, y_size = self.size
        self.matrix = [[FIELD_WEIGHT for _ in range(y_size)] for _ in range(x_size)]
        used_weapon = WEAPONS_ENCODING.get(self.champion.weapon)
        next_field = self.get_next_field()
        self.matrix[next_field[1]][next_field[0]] = FIELD_WEIGHT / 2

        self.effect_weight: int = FIELD_ATTACKED
        if self.episode % MIST_TTH == 0:
            self.increase_mist()
        self.episode += 1
        for position, tileDescription in knowledge.visible_tiles.items():
            if tileDescription.character and tileDescription.character != self.champion:
                self.champions[tileDescription.character] = (position, 0)

        for character, tere in self.champions.items():
            position, age = tere

            y, x = position
            self.matrix[x][y] = age * FIELD_ATTACKED

            aged_value = int(FIELD_ATTACKED / (age + 1))
            self.effect_weight = max(aged_value, FIELD_WEIGHT)
            weapon = WEAPONS_MAP.get(character.weapon)
            weapon.cut(self, position, character.facing)
            self.effect_weight = max(aged_value / 2, FIELD_WEIGHT)
            weapon.cut(self, position, character.facing.turn_left())
            weapon.cut(self, position, character.facing.turn_right())

        for position, tileDescription in {**self.terrain, **self.tiles_memory}.items():
            y, x = position
            if not TILES_MAP.get(tileDescription.type).terrain_passable():
                self.matrix[x][y] = 0
            elif self.matrix[x][y] == FIELD_WEIGHT:
                if tileDescription.loot:
                    importance = WEAPONS_ENCODING.get(tileDescription.loot)
                    if importance > used_weapon:
                        self.matrix[x][y] = importance
                    else:
                        self.matrix[x][y] = importance * FIELD_WEIGHT

    def find_move_to_menhir(self) -> characters.Action:
        grid = Grid(matrix=self.matrix)
        start = grid.node(*self.position)
        for possible_postion in Facing:
            end_position = self.menhir_position + possible_postion.value
            if end_position == start:
                return characters.Action.TURN_LEFT
            end = grid.node(*(self.menhir_position + possible_postion.value))
            path, _ = finder.find_path(start, end, grid)
            if len(path) > 1:
                if self.get_next_field() == path[1]:
                    return characters.Action.STEP_FORWARD
                if self.get_right_field() == path[1]:
                    return characters.Action.TURN_RIGHT
        return characters.Action.TURN_LEFT

    def register_effect(self, _, coords: coordinates.Coords) -> None:
        y, x = coords
        self.matrix[x][y] = self.effect_weight

    def get_field_value(self, coords: coordinates.Coords):
        y, x = coords
        return self.matrix[x][y]

    def check_if_passable_safely(self, coords: coordinates.Coords) -> bool:
        value = self.get_field_value(coords)
        return value != FIELD_ATTACKED and value > 0

    def find_escape_action(self) -> characters.Action:
        if self.check_if_passable_safely(self.get_left_field()):
            return characters.Action.TURN_LEFT
        elif self.check_if_passable_safely(self.get_right_field()):
            return characters.Action.TURN_RIGHT
        return None


class ShallowMindController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.prev_champion: ChampionDescription = None
        self.arena: ArenaMapped = None
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()

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
        self.prev_champion = self.arena.champion
        self.arena.prepare_matrix(knowledge)

        if not self.action_queue.empty():
            return self.action_queue.get()

        champ = self.arena.champion
        if self.prev_champion:
            if champ.health != self.prev_champion.health:
                action = self.arena.find_escape_action()
                if action:
                    self.action_queue.put(characters.Action.STEP_FORWARD)
                    return action
        action = self.arena.find_move_to_menhir()
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
