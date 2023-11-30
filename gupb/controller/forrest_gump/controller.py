from random import choice

import numpy as np
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.controller import Controller
from gupb.controller.forrest_gump.utils import init_grid, next_pos_to_action, is_facing, closest_opposite
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
    'knife': 1,
    'sword': 2,
    'axe': 3,
    'bow': 4,
    'bow_loaded': 4,
    'bow_unloaded': 4,
    'amulet': 5
}


class ForrestGumpController(Controller):
    def __init__(self, first_name: str) -> None:
        self.first_name = first_name

        self.attack_distance = 3
        self.attack_health = 2
        self.defend_distance = 5
        self.go_to_menhir_if_alive = 1
        self.hide_distance = 5
        self.pickup_distance = 5
        self.potion_distance = 5

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ForrestGumpController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def find_nearest_field_from_list(self, position: coordinates.Coords, fields: np.ndarray, knowledge: characters.ChampionKnowledge) -> coordinates.Coords:
        position = np.array([position.x, position.y])

        for new_x, new_y in fields[np.argsort(np.abs(fields - position).sum(axis=1))]:
            coords = coordinates.Coords(new_x, new_y)

            if [new_x, new_y] in self.fields and (coords not in knowledge.visible_tiles or not knowledge.visible_tiles[coords].character):
                return coordinates.Coords(new_x, new_y)

        return coordinates.Coords(*position)

    def find_path(self, position: coordinates.Coords, destination: coordinates.Coords) -> list:
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        grid = Grid(matrix=self.matrix)

        start = grid.node(position.x, position.y)
        finish = grid.node(destination.x, destination.y)

        return finder.find_path(start, finish, grid)[0]

    def distance(self, position: coordinates.Coords, destination: coordinates.Coords) -> int:
        return len(self.find_path(position, destination)) - 1

    def grab_potion(self, position: coordinates.Coords, destination: coordinates.Coords, tile: tiles.TileDescription) -> bool:
        return tile.consumable and self.distance(position, destination) <= self.potion_distance

    def grab_weapon(self, position: coordinates.Coords, destination: coordinates.Coords, weapon: str, tile: tiles.TileDescription) -> bool:
        return (tile.loot and self.distance(position, destination) <= self.pickup_distance and
                WEAPONS_VALUE[weapon] < WEAPONS_VALUE[tile.loot.name])

    def go_to_destination(self, position: coordinates.Coords, facing: characters.Facing) -> characters.Action:
        path = self.find_path(position, self.destination_coords)
        next_pos = path[1] if len(path) > 1 else path[0]
        self.destination_age -= 1
        return next_pos_to_action(next_pos.x, next_pos.y, facing, position, self.fast and len(path) > 2)

    def cut_positions(self, position: coordinates.Coords, facing: characters.Facing, weapon: str) -> list:
        return WEAPONS[weapon].cut_positions(self.arena.terrain, position, facing)

    def set_destination(self, destination: coordinates.Coords, max_age: int, fast: bool) -> None:
        if self.override:
            self.destination_coords = destination
            self.destination_age = max_age
            self.fast = fast
            self.override = False

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        character = knowledge.visible_tiles[knowledge.position].character
        position = knowledge.position
        weapon = character.weapon.name
        facing = character.facing
        health = character.health

        nearest_mist_distance = float('inf')
        nearest_mist_coords = None

        if (self.final_coords and knowledge.no_of_champions_alive <= self.go_to_menhir_if_alive and
                self.distance(position, self.final_coords) > self.defend_distance):
            self.set_destination(self.final_coords, 50, False)
        elif self.destination_age <= 0 or position == self.destination_coords:
            x, y = choice(self.fields)
            self.set_destination(coordinates.Coords(x, y), 30, False)

        self.override = True

        tiles = np.array([tile for tile in knowledge.visible_tiles])
        order = np.argsort(np.abs(tiles - np.array([position.x, position.y])).sum(axis=1))
        tiles = tiles[order]

        for x, y in tiles:
            tile = knowledge.visible_tiles[coordinates.Coords(x, y)]
            coords = coordinates.Coords(x, y)

            if coords == position:
                continue

            if tile.character:
                cut_positions = self.cut_positions(position, facing, weapon)

                if 'bow' in weapon and self.distance(position, coords) >= 3 and coords in cut_positions:
                    return characters.Action.ATTACK

                if (health + self.attack_health >= tile.character.health and
                        ('bow' not in weapon or 'bow' in weapon and (self.distance(position, coords) >= 4 or
                         health + 2 * self.attack_health >= tile.character.health))):
                    if coords in cut_positions:
                        return characters.Action.ATTACK
                    elif self.distance(position, coords) <= self.attack_distance:
                        if weapon == 'amulet':
                            possible_pos = np.array([[1, 1], [1, -1], [-1, 1], [-1, -1], [2, 2], [2, -2], [-2, 2], [-2, -2]]) + np.array([x, y])
                            self.set_destination(self.find_nearest_field_from_list(position, possible_pos, knowledge), 10, True)
                        else:
                            self.set_destination(coords, 10, True)
                elif coords in cut_positions and not is_facing(position, coords, tile.character.facing):
                    return characters.Action.ATTACK
                elif self.distance(position, coords) <= self.hide_distance:
                    cut_positions = WEAPONS[tile.character.weapon.name].cut_positions(self.arena.terrain, coords, tile.character.facing)

                    if position in cut_positions:
                        safe_positions = self.fields.copy()

                        for pos in cut_positions:
                            if pos in safe_positions:
                                safe_positions.remove([pos.x, pos.y])

                        safe_positions = [coordinates.Coords(pos[0], pos[1]) for pos in safe_positions]
                        new_coords = min([(self.distance(position, pos), pos) for pos in safe_positions])[1]
                    else:
                        new_coords = closest_opposite(self.fields, position, coords)
                        new_coords = coordinates.Coords(new_coords[0], new_coords[1])

                    self.set_destination(new_coords, 10, True)

            if self.grab_potion(position, coords, tile):
                self.set_destination(coords, 10, True)

            if self.grab_weapon(position, coords, weapon, tile):
                self.set_destination(coords, 10, False)

            if not self.final_coords:
                if tile.type == 'menhir':
                    self.final_coords = coords

            if (any(effect.type == 'mist' for effect in tile.effects) and
                    (dist := self.distance(position, coords)) < nearest_mist_distance):
                nearest_mist_distance = dist
                nearest_mist_coords = coords

        self.override = True

        if nearest_mist_coords:
            if self.final_coords:
                if position == self.final_coords:
                    return characters.Action.TURN_LEFT
                self.set_destination(self.final_coords, 10, False)
            else:
                new_pos = closest_opposite(self.fields, position, nearest_mist_coords)
                new_pos = coordinates.Coords(new_pos[0], new_pos[1])
                self.set_destination(new_pos, 10, False)

        return self.go_to_destination(position, facing)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena = arenas.Arena.load(arena_description.name)
        self.matrix = init_grid(arena_description)
        self.fields = np.argwhere(self.matrix.T == 1).tolist()

        self.fast = False
        self.final_coords = None
        self.destination_coords = None
        self.destination_age = 0
        self.override = True

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ORANGE
