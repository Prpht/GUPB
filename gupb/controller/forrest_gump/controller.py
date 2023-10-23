import numpy as np
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.controller import Controller
from gupb.controller.forrest_gump.utils import init_grid, next_pos_to_action
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import effects
from gupb.model import weapons


WEAPONS = {
    'knife': weapons.Knife,
    'sword': weapons.Sword,
    'bow': weapons.Bow,
    'bow_loaded': weapons.Bow,
    'bow_unloaded': weapons.Bow,
    'axe': weapons.Axe,
    'amulet': weapons.Amulet
}

WEAPONS_VALUE = {
    'knife': 1,
    'sword': 2,
    'axe': 3,
    'amulet': 4,
    'bow': 5,
    'bow_loaded': 5,
    'bow_unloaded': 5
}


class ForrestGumpController(Controller):
    MAX_DESTINATION_AGE = 30
    PICKUP_DISTANCE = 5
    POTION_DISTANCE = 3

    def __init__(self, first_name: str) -> None:
        self.first_name = first_name

        self.arena = None
        self.matrix = None
        self.fields = None

        self.final_coords = None
        self.destination_coords = None
        self.destination_age = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ForrestGumpController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def go_to_destination(self, position: coordinates.Coords, facing: characters.Facing) -> characters.Action:
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        grid = Grid(matrix=self.matrix)

        start = grid.node(position.x, position.y)
        finish = grid.node(self.destination_coords.x, self.destination_coords.y)
        path, _ = finder.find_path(start, finish, grid)

        next_pos = path[1] if len(path) > 1 else path[0]
        return next_pos_to_action(next_pos.x, next_pos.y, facing, position)

    @staticmethod
    def manhattan_distance(coords: coordinates.Coords, x: int, y: int) -> int:
        return np.abs(coords.x - x) + np.abs(coords.y - y)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        my_character = knowledge.visible_tiles[knowledge.position].character
        my_position = knowledge.position
        cut_positions = WEAPONS[my_character.weapon.name].cut_positions(self.arena.terrain, my_position, my_character.facing)

        for (x, y), tile in knowledge.visible_tiles.items():
            if tile.character and coordinates.Coords(x, y) in cut_positions:
                return characters.Action.ATTACK
            elif not self.final_coords:
                if tile.type == 'menhir':
                    self.destination_coords = coordinates.Coords(x, y)
                    self.final_coords = coordinates.Coords(x, y)
                elif any(isinstance(e, effects.Mist) for e in tile.effects):
                    dx, dy = knowledge.position.x - x, knowledge.position.y - y
                    self.destination_coords = coordinates.Coords(knowledge.position.x + dx, knowledge.position.y + dy)
                    self.destination_age = 0
                elif (tile.loot and self.manhattan_distance(my_position, x, y) <= self.PICKUP_DISTANCE and
                      WEAPONS_VALUE[my_character.weapon.name] < WEAPONS_VALUE[tile.loot.name] or
                        tile.consumable and self.manhattan_distance(my_position, x, y) <= self.POTION_DISTANCE):
                    self.destination_coords = coordinates.Coords(x, y)
                    self.destination_age = 0

        if my_position == self.final_coords:
            return np.random.choice([characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT])

        if (not self.destination_coords or
                self.destination_age > self.MAX_DESTINATION_AGE or
                knowledge.position == self.destination_coords):
            y, x = self.fields[np.random.choice(self.fields.shape[0])]
            self.destination_coords = coordinates.Coords(x, y)
            self.destination_age = 0

        self.destination_age += 1

        return self.go_to_destination(my_position, my_character.facing)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena = arenas.Arena.load(arena_description.name)
        self.matrix = init_grid(arena_description)
        self.fields = np.argwhere(self.matrix == 1)

        self.final_coords = None
        self.destination_coords = None
        self.destination_age = 0

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ORANGE
