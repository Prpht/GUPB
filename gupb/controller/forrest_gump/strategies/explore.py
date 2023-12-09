from random import choice

from gupb.controller.forrest_gump.strategies import Strategy
from gupb.controller.forrest_gump.utils import CharacterInfo, find_path, next_pos_to_action
from gupb.model import arenas, characters, coordinates, tiles


class Explore(Strategy):
    def __init__(self, arena_description: arenas.ArenaDescription, max_age: int) -> None:
        super().__init__(arena_description)
        self.max_age = max_age
        self.destination = None

        self.lu_corner = min(self.fields, key=lambda c: c[0] + c[1])
        self.ru_corner = min(self.fields, key=lambda c: c[0] - c[1])
        self.rd_corner = max(self.fields, key=lambda c: c[0] + c[1])
        self.ld_corner = max(self.fields, key=lambda c: c[0] - c[1])

        self.corners = [self.lu_corner, self.ru_corner, self.rd_corner, self.ld_corner]

    def new_destination(self) -> None:
        self.destination = coordinates.Coords(*choice(self.corners))
        self.destination_age = 0

    def enter(self) -> None:
        self.new_destination()

    def should_enter(self, coords: coordinates.Coords, tile: tiles.TileDescription, character_info: CharacterInfo) -> bool:
        if self.destination is None:
            closest_corner = min(self.corners, key=lambda c: c.manhattan_distance(character_info.position))
            self.destination = closest_corner
            self.destination_age = 0

        return True

    def should_leave(self, character_info: CharacterInfo) -> bool:
        return False

    def left(self) -> None:
        self.new_destination()

    def next_action(self, character_info: CharacterInfo) -> characters.Action:
        if character_info.position == self.destination or self.destination_age >= self.max_age:
            self.new_destination()

        path = find_path(self.matrix, character_info.position, self.destination)
        next_pos = path[1] if len(path) > 1 else path[0]
        self.destination_age += 1

        return next_pos_to_action(next_pos.x, next_pos.y, character_info.facing, character_info.position, False)

    @property
    def priority(self) -> int:
        return 0
