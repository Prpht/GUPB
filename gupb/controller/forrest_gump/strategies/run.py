from gupb.controller.forrest_gump.strategies import Strategy
from gupb.controller.forrest_gump.utils import CharacterInfo, manhattan_distance_to, next_pos_to_action, find_path, closest_opposite
from gupb.model import tiles, coordinates, characters, arenas


class Run(Strategy):
    def __init__(self, arena_description: arenas.ArenaDescription, close_distance: int, far_distance: int, distance_to_menhir: int) -> None:
        super().__init__(arena_description)
        self.close_distance = close_distance
        self.far_distance = far_distance
        self.distance_to_menhir = distance_to_menhir

    def enter(self) -> None:
        pass

    def should_enter(self, coords: coordinates.Coords, tile: tiles.TileDescription, character_info: CharacterInfo) -> bool:
        self.character_info = character_info

        if any(effect.type == 'mist' for effect in tile.effects):
            if character_info.menhir and manhattan_distance_to(character_info.menhir, character_info.position) <= self.distance_to_menhir:
                return False

            self.mist = coords
            return True

        return False

    def should_leave(self, character_info: CharacterInfo) -> bool:
        self.character_info = character_info

        return (manhattan_distance_to(self.mist, character_info.position) >= self.far_distance or
                   character_info.menhir and manhattan_distance_to(character_info.menhir, character_info.position) <= self.distance_to_menhir)

    def left(self) -> None:
        pass

    def next_action(self, character_info: CharacterInfo) -> characters.Action:
        self.character_info = character_info

        if character_info.menhir and character_info.menhir == character_info.position:
            return characters.Action.TURN_LEFT

        if character_info.menhir:
            destination = character_info.menhir
        else:
            destination = closest_opposite(self.fields, character_info.position, self.mist)
            destination = coordinates.Coords(destination[0], destination[1])

        path = find_path(self.matrix, character_info.position, destination)
        next_pos = path[1] if len(path) > 1 else path[0]
        return next_pos_to_action(next_pos.x, next_pos.y, character_info.facing, character_info.position, False)

    @property
    def priority(self) -> int:
        if manhattan_distance_to(self.character_info.position, self.mist) <= self.close_distance:
            return 5
        else:
            return 2
