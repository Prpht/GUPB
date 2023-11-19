from random import choice

import numpy as np
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.controller import Controller
from gupb.controller.forrest_gump.utils import init_grid, next_pos_to_action, is_facing
from gupb.controller.forrest_gump.egreedy import EGreedy
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
    'axe': 4,
    'amulet': 5,
    'bow': 3,
    'bow_loaded': 3,
    'bow_unloaded': 3
}


class ForrestGumpController(Controller):
    def __init__(self, first_name: str) -> None:
        self.first_name = first_name

        self.attack_distance_agent = EGreedy(n_arms=5, epsilon=0.03, optimistic_start=200., offset=1)
        self.attack_health_agent = EGreedy(n_arms=5, epsilon=0.03, optimistic_start=200., offset=0)
        self.defend_distance_agent = EGreedy(n_arms=5, epsilon=0.03, optimistic_start=200., offset=4)
        self.go_to_menhir_if_alive_agent = EGreedy(n_arms=7, epsilon=0.03, optimistic_start=200., offset=1)
        self.hide_distance_agent = EGreedy(n_arms=6, epsilon=0.03, optimistic_start=200., offset=2)
        self.pickup_distance_agent = EGreedy(n_arms=8, epsilon=0.03, optimistic_start=200., offset=1)
        self.potion_distance_agent = EGreedy(n_arms=7, epsilon=0.03, optimistic_start=200., offset=1)

        self.attack_distance = self.attack_distance_agent(0.)
        self.attack_health = self.attack_health_agent(0.)
        self.defend_distance = self.defend_distance_agent(0.)
        self.go_to_menhir_if_alive = self.go_to_menhir_if_alive_agent(0.)
        self.hide_distance = self.hide_distance_agent(0.)
        self.pickup_distance = self.pickup_distance_agent(0.)
        self.potion_distance = self.potion_distance_agent(0.)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ForrestGumpController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def find_nearest_field(self, position: coordinates.Coords) -> tuple:
        position = np.array([position.x, position.y])
        return self.fields_copy[np.argmin(np.abs(self.fields_copy - position).sum(axis=1))]

    def find_nearest_field_from_list(self, position: coordinates.Coords, fields: np.ndarray, knowledge: characters.ChampionKnowledge) -> coordinates.Coords:
        position = np.array([position.x, position.y])

        for new_x, new_y in fields[np.argsort(np.abs(fields - position).sum(axis=1))]:
            coords = coordinates.Coords(new_x, new_y)

            if [new_x, new_y] in self.fields_copy and (coords not in knowledge.visible_tiles or not knowledge.visible_tiles[coords].character):
                return coordinates.Coords(new_x, new_y)

        return coordinates.Coords(*position)

    def find_path(self, position: coordinates.Coords, destination: coordinates.Coords) -> list:
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        grid = Grid(matrix=self.matrix)

        start = grid.node(position.x, position.y)
        finish = grid.node(*self.find_nearest_field(destination))

        return finder.find_path(start, finish, grid)[0]

    def distance(self, position: coordinates.Coords, destination: coordinates.Coords) -> int:
        return len(self.find_path(position, destination)) - 1

    def grab_potion(self, position: coordinates.Coords, destination: coordinates.Coords, tile: tiles.TileDescription) -> bool:
        return tile.consumable and self.distance(position, destination) <= self.potion_distance

    def grab_weapon(self, position: coordinates.Coords, destination: coordinates.Coords, weapon: str, tile: tiles.TileDescription) -> bool:
        return (tile.loot and self.distance(position, destination) <= self.pickup_distance and
                WEAPONS_VALUE[weapon] < WEAPONS_VALUE[tile.loot.name])

    def go_to_destination(self, position: coordinates.Coords, facing: characters.Facing) -> characters.Action:
        while coordinates.Coords(*self.find_nearest_field(self.destination_coords)) == position:
            x, y = choice(self.fields)
            self.set_destination(coordinates.Coords(x, y), 10, self.fast)

        path = self.find_path(position, self.destination_coords)
        next_pos = path[1] if len(path) > 1 else path[0]
        self.destination_age -= 1
        return next_pos_to_action(next_pos.x, next_pos.y, facing, position, self.fast and len(path) > 2)

    def cut_positions(self, position: coordinates.Coords, facing: characters.Facing, weapon: str) -> list:
        return WEAPONS[weapon].cut_positions(self.arena.terrain, position, facing)

    @staticmethod
    def opposite_direction(position: coordinates.Coords, destination: coordinates.Coords) -> coordinates.Coords:
        dx, dy = position.x - destination.x, position.y - destination.y
        return coordinates.Coords(position.x + dx, position.y + dy)

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
                if (health + self.attack_health >= tile.character.health and
                        ('bow' not in weapon or 'bow' in weapon and (self.distance(position, coords) >= 4 or
                         2 * health + self.attack_health >= tile.character.health))):
                    if coords in self.cut_positions(position, facing, weapon):
                        return characters.Action.ATTACK
                    elif self.distance(position, coords) <= self.attack_distance:
                        if weapon == 'amulet':
                            possible_pos = np.array([[1, 1], [1, -1], [-1, 1], [-1, -1], [2, 2], [2, -2], [-2, 2], [-2, -2]]) + np.array([x, y])
                            self.set_destination(self.find_nearest_field_from_list(position, possible_pos, knowledge), 10, True)
                        else:
                            self.set_destination(coords, 10, True)
                elif self.distance(position, coords) <= self.hide_distance and is_facing(position, coords, tile.character.facing):
                    if tile.character.weapon.name == 'amulet':
                        possible_pos = np.array([
                            [1, 0], [-1, 0], [0, 1], [0, -1], [2, 0], [-2, 0], [0, 2], [0, -2],
                            [2, 1], [2, -1], [-2, 1], [-2, -1], [1, 2], [1, -2], [-1, 2], [-1, -2],
                        ]) + np.array([x, y])
                        self.set_destination(self.find_nearest_field_from_list(position, possible_pos, knowledge), 10, True)
                    elif (position.x == x and
                            (position.y > y and tile.character.facing == characters.Facing.DOWN or
                             position.y < y and tile.character.facing == characters.Facing.UP)):
                        possible_pos = np.array([[-1, -1], [-1, 0], [-1, 1], [1, -1], [1, 0], [1, 1]]) + np.array([position.x, position.y])
                        self.set_destination(self.find_nearest_field_from_list(position, possible_pos, knowledge), 10, True)
                    elif (position.y == y and
                            (position.x > x and tile.character.facing == characters.Facing.RIGHT or
                             position.x < x and tile.character.facing == characters.Facing.LEFT)):
                        possible_pos = np.array([[-1, -1], [0, -1], [1, -1], [-1, 1], [0, 1], [1, 1]]) + np.array([position.x, position.y])
                        self.set_destination(self.find_nearest_field_from_list(position, possible_pos, knowledge), 10, True)
                    else:
                        new_coords = self.opposite_direction(position, coords)
                        self.set_destination(new_coords, 10, True)

            if self.grab_potion(position, coords, tile):
                self.set_destination(coords, 10, True)

            if self.grab_weapon(position, coords, weapon, tile):
                self.set_destination(coords, 10, False)

            if not self.final_coords:
                if tile.type == 'menhir':
                    self.fields = self.fields_copy
                    self.final_coords = coords
                else:
                    try:
                        self.fields.remove([x, y])
                    except ValueError:
                        pass

            if (any(effect.type == 'mist' for effect in tile.effects) and
                    (dist := self.distance(position, coords)) < nearest_mist_distance):
                nearest_mist_distance = dist
                nearest_mist_coords = coords

        self.override = True

        if nearest_mist_coords:
            if self.final_coords:
                if position == self.final_coords:
                    return characters.Action.TURN_LEFT
                self.set_destination(self.final_coords, 10, True)
            else:
                new_pos = self.opposite_direction(position, nearest_mist_coords)
                self.set_destination(new_pos, 10, True)

        return self.go_to_destination(position, facing)

    def praise(self, score: int) -> None:
        self.attack_distance = self.attack_distance_agent(score)
        self.attack_health = self.attack_health_agent(score)
        self.defend_distance = self.defend_distance_agent(score)
        self.go_to_menhir_if_alive = self.go_to_menhir_if_alive_agent(score)
        self.hide_distance = self.hide_distance_agent(score)
        self.pickup_distance = self.pickup_distance_agent(score)
        self.potion_distance = self.potion_distance_agent(score)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena = arenas.Arena.load(arena_description.name)
        self.matrix = init_grid(arena_description)
        self.fields = np.argwhere(self.matrix.T == 1).tolist()
        self.fields_copy = self.fields.copy()

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
