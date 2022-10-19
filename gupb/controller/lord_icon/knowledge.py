import numpy as np
from gupb.controller.lord_icon.distance import Point2d, heuristic
from gupb.controller.lord_icon.weapons import ALL_WEAPONS

from gupb.model.arenas import Arena
from gupb.model import characters, coordinates

from typing import NamedTuple
from collections import defaultdict

MAPPER = defaultdict(lambda: 1, {"land": 0, "menhir": 0})


class CharacterInfo(NamedTuple):
    health: int
    weapon: str
    position: Point2d
    facing: characters.Facing

    @staticmethod
    def from_tile(tile, position):
        return CharacterInfo(
            health=tile.character.health,
            weapon=tile.character.weapon.name,
            position=position,
            facing=tile.character.facing,
        )

    def distance(self, other):
        return heuristic(self.position, other.position)

    def get_attack_range(self, map):
        if self.weapon in ALL_WEAPONS:
            return ALL_WEAPONS[self.weapon].get_attack_range(
                map, self.facing, self.position
            )
        return []

    def can_attack(self, map, position):
        return position in self.get_attack_range(map)

    def predict_move(self, map):
        face_x, face_y = self.facing.value
        x, y = self.position
        predicted_moves = [self.position]
        if map[x + face_x, y + face_y] == 0:
            predicted_moves.append((x + face_x, y + face_y))

        return predicted_moves

    def predict_attack_range(self, map):
        points = []
        for position in self.predict_move(map):
            for facing in characters.Facing:
                points += CharacterInfo(
                    health=self.health,
                    weapon=self.weapon,
                    position=position,
                    facing=facing,
                ).get_attack_range(map)
        return points


def parse_coords(coord):
    return (
        (coord.x, coord.y)
        if isinstance(coord, coordinates.Coords)
        else (coord[0], coord[1])
    )


class Knowledge:
    def __init__(self):
        self.position = None
        self.arena = None
        self.map = None
        self.menhir = None
        self.character = None
        self.weapons = {}
        self.enemies = []
        self.initial_weapons_positions = []

    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position.x, knowledge.position.y

        # Load weapons only once after restart, during first update
        if len(self.initial_weapons_positions) > 0:
            for pos, name in self.initial_weapons_positions:
                self.weapons[pos] = heuristic(pos, self.position) - ALL_WEAPONS[name].value
            self.initial_weapons_positions = []

        self.enemies = []

        for coord, tile in knowledge.visible_tiles.items():
            x, y = parse_coords(coord)

            if self.position == (x, y):
                self.character = CharacterInfo.from_tile(tile, (x, y))
            else:
                if tile.character:
                    self.enemies.append(CharacterInfo.from_tile(tile, (x, y)))
                elif tile.loot and tile.loot.name != 'knife':
                    self.weapons[(x, y)] = heuristic((x, y), self.position) - ALL_WEAPONS[tile.loot.name].value
            if tile.type == "menhir":
                self.menhir = (x, y)

            # Update map
            self.map[x, y] = MAPPER[tile.type]
            if tile.loot and ALL_WEAPONS[tile.loot.name].value <= ALL_WEAPONS[self.character.weapon].value:
                self.map[x, y] = 1

    def reset(self, arena_name):
        self.arena = Arena.load(arena_name)
        n, m = self.arena.size
        self.map = np.ones((n, m))

        for position, tile in self.arena.terrain.items():
            self.map[position.x, position.y] = MAPPER[tile.description().type]
            if tile.loot:
                self.initial_weapons_positions.append((position, tile.loot.description().name))

        self.position = None
        self.menhir = None
