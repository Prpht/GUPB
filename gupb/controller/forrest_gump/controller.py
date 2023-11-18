from random import choice

import numpy as np
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.controller import Controller
from gupb.controller.forrest_gump.utils import init_grid, next_pos_to_action, next_facing
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import weapons
from gupb.model import tiles


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
    'knife': 2,
    'sword': 3,
    'axe': 5,
    'amulet': 4,
    'bow': 1,
    'bow_loaded': 1,
    'bow_unloaded': 1
}


class ForrestGumpController(Controller):
    PICKUP_DISTANCE = 5
    POTION_DISTANCE = 5
    ATTACK_DISTANCE = 4
    HIDE_DISTANCE = 3
    DEFEND_DISTANCE = 3

    def __init__(self, first_name: str) -> None:
        self.first_name = first_name

        self.arena = None
        self.matrix = None
        self.fields = None
        self.fields_copy = None

        self.final_coords = None
        self.destination_coords = None
        self.destination_age = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ForrestGumpController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def find_nearest_field(self, position: coordinates.Coords) -> tuple:
        position = np.array([position.x, position.y])
        return self.fields_copy[np.argmin(np.abs(self.fields_copy - position).sum(axis=1))]

    def find_path(self, position: coordinates.Coords, destination: coordinates.Coords) -> list:
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        grid = Grid(matrix=self.matrix)

        start = grid.node(position.x, position.y)
        finish = grid.node(*self.find_nearest_field(destination))

        return finder.find_path(start, finish, grid)[0]

    def distance(self, position: coordinates.Coords, destination: coordinates.Coords) -> int:
        return len(self.find_path(position, destination)) - 1

    def grab_item(self, position: coordinates.Coords, destination: coordinates.Coords, weapon: str, tile: tiles.TileDescription) -> bool:
        return ((tile.loot and self.distance(position, destination) <= self.PICKUP_DISTANCE and
                WEAPONS_VALUE[weapon] < WEAPONS_VALUE[tile.loot.name]) or
                (tile.consumable and self.distance(position, destination) <= self.POTION_DISTANCE))

    def go_to_destination(self, position: coordinates.Coords, facing: characters.Facing) -> characters.Action:
        path = self.find_path(position, self.destination_coords)
        next_pos = path[1] if len(path) > 1 else path[0]
        self.destination_age -= 1
        return next_pos_to_action(next_pos.x, next_pos.y, facing, position)

    def cut_positions(self, position: coordinates.Coords, facing: characters.Facing, weapon: str) -> list:
        return WEAPONS[weapon].cut_positions(self.arena.terrain, position, facing)

    @staticmethod
    def opposite_direction(position: coordinates.Coords, destination: coordinates.Coords) -> coordinates.Coords:
        dx, dy = position.x - destination.x, position.y - destination.y
        return coordinates.Coords(position.x + 2 * dx, position.y + 2 * dy)

    def set_destination(self, destination: coordinates.Coords, override: bool, max_age: int) -> None:
        if override:
            self.destination_coords = destination
            self.destination_age = max_age

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        character = knowledge.visible_tiles[knowledge.position].character
        position = knowledge.position
        weapon = character.weapon.name
        facing = character.facing

        nearest_mist_distance = float('inf')
        nearest_mist_coords = None
        override = True

        if self.final_coords and self.distance(position, self.final_coords) > self.DEFEND_DISTANCE:
            self.set_destination(self.final_coords, override, 50)
        elif self.destination_age <= 0 or position == self.destination_coords:
            x, y = choice(self.fields)
            self.set_destination(coordinates.Coords(x, y), override, 30)

        for (x, y), tile in knowledge.visible_tiles.items():
            coords = coordinates.Coords(x, y)

            if coords == position:
                continue

            if tile.character:
                if (coords in self.cut_positions(position, facing, weapon) and
                        position not in self.cut_positions(coords, tile.character.facing, tile.character.weapon.name)):
                    return characters.Action.ATTACK

                if character.health + 3 >= tile.character.health or character.health >= 6:
                    if coords in self.cut_positions(position, facing, weapon):
                        return characters.Action.ATTACK
                    elif coords in self.cut_positions(position, next_facing(facing, characters.Action.TURN_LEFT), weapon):
                        return characters.Action.TURN_LEFT
                    elif coords in self.cut_positions(position, next_facing(facing, characters.Action.TURN_RIGHT), weapon):
                        return characters.Action.TURN_RIGHT
                    elif self.distance(position, coords) <= self.ATTACK_DISTANCE:
                        if weapon == 'amulet':
                            possible_pos = np.array([
                                [x + 1, y + 1], [x + 1, y - 1], [x - 1, y + 1], [x - 1, y - 1],
                                [x + 2, y + 2], [x + 2, y - 2], [x - 2, y + 2], [x - 2, y - 2],
                            ])

                            for new_x, new_y in possible_pos[np.argsort(np.abs(possible_pos - position).sum(axis=1))]:
                                if [new_x, new_y] in self.fields:
                                    self.set_destination(coordinates.Coords(new_x, new_y), override, 10)
                                    override = False
                        else:
                            self.set_destination(coords, override, 10)
                            override = False

                if (position in self.cut_positions(coords, tile.character.facing, tile.character.weapon.name) or
                        self.distance(position, coords) <= self.HIDE_DISTANCE):
                    if tile.character.weapon.name == 'amulet':
                        possible_pos = np.array([
                            [x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1],
                            [x + 2, y], [x - 2, y], [x, y + 2], [x, y - 2],
                            [x + 2, y + 1], [x + 2, y - 1], [x - 2, y + 1], [x - 2, y - 1],
                            [x + 1, y + 2], [x + 1, y - 2], [x - 1, y + 2], [x - 1, y - 2],
                        ])

                        for new_x, new_y in possible_pos[np.argsort(np.abs(possible_pos - position).sum(axis=1))]:
                            if [new_x, new_y] in self.fields:
                                self.set_destination(coordinates.Coords(new_x, new_y), override, 10)
                                override = False
                    else:
                        new_coords = self.opposite_direction(position, coords)

                        if new_coords.x == x and (tile.character.facing == characters.Facing.UP or tile.character.facing == characters.Facing.DOWN):
                            for new_x, new_y in [[new_coords.x + 1, new_coords.y], [new_coords.x - 1, new_coords.y]]:
                                if [new_x, new_y] in self.fields:
                                    self.set_destination(coordinates.Coords(new_x, new_y), override, 10)
                                    override = False
                        elif new_coords.y == y and (tile.character.facing == characters.Facing.LEFT or tile.character.facing == characters.Facing.RIGHT):
                            for new_x, new_y in [[new_coords.x, new_coords.y + 1], [new_coords.x, new_coords.y - 1]]:
                                if [new_x, new_y] in self.fields:
                                    self.set_destination(coordinates.Coords(new_x, new_y), override, 10)
                                    override = False
                        else:
                            self.set_destination(new_coords, override, 10)
                            override = False

            if self.grab_item(position, coords, weapon, tile):
                self.set_destination(coords, override, 10)
                override = False

            if not self.final_coords:
                if tile.type == 'menhir':
                    self.fields = self.fields_copy
                    self.final_coords = coords
                    self.set_destination(coords, override, 50)
                else:
                    try:
                        self.fields.remove([x, y])
                    except ValueError:
                        pass

            if (any(effect.type == 'mist' for effect in tile.effects) and
                    (dist := self.distance(position, coords)) < nearest_mist_distance):
                nearest_mist_distance = dist
                nearest_mist_coords = coords

        if nearest_mist_coords:
            if self.final_coords:
                if position == self.final_coords:
                    return characters.Action.TURN_LEFT
                self.set_destination(self.final_coords, True, 10)
            else:
                new_pos = self.opposite_direction(position, nearest_mist_coords)
                self.set_destination(new_pos, True, 10)

        while coordinates.Coords(*self.find_nearest_field(self.destination_coords)) == position:
            x, y = choice(self.fields)
            self.set_destination(coordinates.Coords(x, y), True, 30)

        return self.go_to_destination(position, facing)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena = arenas.Arena.load(arena_description.name)
        self.matrix = init_grid(arena_description)
        self.fields = np.argwhere(self.matrix.T == 1).tolist()
        self.fields_copy = self.fields.copy()

        self.final_coords = None
        self.destination_coords = None
        self.destination_age = 0

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ORANGE
