from random import choice, random

from gupb.controller.forrest_gump.strategies import Strategy
from gupb.controller.forrest_gump.utils import CharacterInfo, find_path, next_pos_to_action
from gupb.model import arenas, characters, coordinates, tiles


class Explore(Strategy):
    def __init__(self, arena_description: arenas.ArenaDescription, max_age: int, no_alive: int, defend_distance: int) -> None:
        super().__init__(arena_description)
        self.max_age = max_age
        self.no_alive = no_alive
        self.defend_distance = defend_distance

        self.destination = None
        self.defense = False

        self.lu_corner = min(self.fields, key=lambda c: c[0] + c[1])
        self.ru_corner = min(self.fields, key=lambda c: c[0] - c[1])
        self.rd_corner = max(self.fields, key=lambda c: c[0] + c[1])
        self.ld_corner = max(self.fields, key=lambda c: c[0] - c[1])

        self.corners = [self.lu_corner, self.ru_corner, self.rd_corner, self.ld_corner]

    def enter(self) -> None:
        pass

    def should_enter(self, coords: coordinates.Coords, tile: tiles.TileDescription, character_info: CharacterInfo) -> bool:
        return True

    def should_leave(self, character_info: CharacterInfo) -> bool:
        return False

    def left(self) -> None:
        pass

    def next_action(self, character_info: CharacterInfo) -> characters.Action:
        if self.defense and character_info.menhir is not None:
            if character_info.position == character_info.menhir:
                self.destination = coordinates.Coords(*choice(self.corners))
                self.destination_age = 0
                self.max_age = self.defend_distance
            elif self.destination_age >= self.max_age:
                self.destination = character_info.menhir
                self.destination_age = -100

        if self.no_alive >= character_info.no_alive and character_info.menhir is not None and not self.defense:
            self.defense = True
            self.destination = character_info.menhir
            self.destination_age = -100

        if self.destination is None or character_info.position == self.destination or self.destination_age >= self.max_age:
            self.destination = coordinates.Coords(*choice(self.corners))
            self.destination_age = 0

        look_around = random()

        if look_around < 0.1:
            return characters.Action.TURN_RIGHT
        elif look_around < 0.2:
            return characters.Action.TURN_LEFT

        path = find_path(self.matrix, character_info.position, self.destination)
        next_pos = path[1] if len(path) > 1 else path[0]
        self.destination_age += 1

        return next_pos_to_action(next_pos.x, next_pos.y, character_info.facing, character_info.position, False)

    @property
    def priority(self) -> int:
        return 0
