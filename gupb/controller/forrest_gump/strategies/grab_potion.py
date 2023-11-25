from gupb.controller.forrest_gump.strategies import Strategy
from gupb.controller.forrest_gump.utils import CharacterInfo, find_path, distance_to, next_pos_to_action
from gupb.model import tiles, coordinates, characters, arenas


class GrabPotion(Strategy):
    def __init__(self, arena_description: arenas.ArenaDescription, max_distance: int = 5) -> None:
        super().__init__(arena_description)
        self.max_distance = max_distance
        self.destination_reached = False

    def enter(self) -> None:
        self.destination_reached = False

    def should_enter(self, coords: coordinates.Coords, tile: tiles.TileDescription, character_info: CharacterInfo) -> bool:
        if tile.consumable and distance_to(self.matrix, coords, character_info.position) <= self.max_distance:
            self.destination = coords
            return True

        return False

    def should_leave(self, character_info: CharacterInfo) -> bool:
        return self.destination_reached

    def left(self) -> None:
        self.destination_reached = False

    def next_action(self, character_info: CharacterInfo) -> characters.Action:
        path = find_path(self.matrix, character_info.position, self.destination)
        next_pos = path[1] if len(path) > 1 else path[0]
        action = next_pos_to_action(next_pos.x, next_pos.y, character_info.facing, character_info.position, False)

        if character_info.position == self.destination or len(path) == 2 and action == characters.Action.STEP_FORWARD:
            self.destination_reached = True

        return action

    @property
    def priority(self) -> int:
        return 4
