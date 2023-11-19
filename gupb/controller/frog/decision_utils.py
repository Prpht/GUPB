from gupb.model.tiles import TileDescription
from typing import Callable, List
from gupb.model.coordinates import Coords
from .utils import manhattan_distance


def is_in_path(position, facing, coordinates_to_check):
    new_position = position + facing.value

    return new_position == coordinates_to_check


def is_safe(tile: TileDescription):
    return len(list(filter(lambda x: x.type == 'mist', tile.effects))) == 0


def has_potion(tile: TileDescription):
    if tile.consumable:
        return tile.consumable.name is 'potion'


def has_weapon(tile: TileDescription):
    if tile.loot:
        return True

    return False


def has_character(tile: TileDescription):
    if tile.character and tile.character.controller_name != 'Frog':
        return True

    return False


def is_menhir(tile: TileDescription):
    return tile.type == 'menhir'


def filter_by_predicate(tile: TileDescription, predicate: Callable[[TileDescription], bool]) -> bool:
    return predicate(tile)


def filter_by_predicates(tile: TileDescription, predicates: List[Callable[[TileDescription], bool]]) -> bool:
    for predicate in predicates:
        if not predicate(tile):
            return False
    return True


def get_menhir(visible_tiles: dict[Coords, TileDescription]) -> Coords:
    tiles = visible_tiles.items()

    filtered = list(filter(lambda x: is_menhir(x[1]), tiles))

    return filtered[0][0] if len(filtered) > 0 else None


def get_nearby_potions(position: Coords, visible_tiles: dict[Coords, TileDescription], distance_threshold=10):
    potion_tiles = filter(lambda item: filter_by_predicates(item[1], [is_safe, has_potion]), visible_tiles.items())

    filtered_tiles = filter(lambda item: manhattan_distance(position, item[0]) <= distance_threshold, potion_tiles)

    sorted_tiles = list(sorted(filtered_tiles, key=lambda item: manhattan_distance(position, item[0])))

    return sorted_tiles


def get_nearby_weapons(position: Coords, visible_tiles: dict[Coords, TileDescription], distance_threshold=5) \
        -> dict[Coords, TileDescription]:
    weapon_tiles = filter(lambda item: filter_by_predicate(item[1], has_weapon), visible_tiles.items())

    filtered_tiles = dict(
        filter(lambda item: manhattan_distance(position, item[0]) <= distance_threshold, weapon_tiles))

    # sorted_tiles = list(sorted(filtered_tiles, key=lambda item: manhattan_distance(position, item[0])))

    return filtered_tiles


def get_nearby_characters(position: Coords, visible_tiles: dict[Coords, TileDescription],
                          distance_threshold=5) -> list:
    tiles = visible_tiles.items()

    char_tiles = filter(lambda item: filter_by_predicate(item[1], has_character), tiles)
    filtered = list(filter(lambda item: manhattan_distance(position, item[0]) <= distance_threshold, char_tiles))

    return filtered if len(filtered) > 0 else None


# noinspection PyChainedComparisons
def get_furthest_coord(position: Coords, visible_tiles: dict[Coords, TileDescription], distance_threshold=5) -> Coords:
    furthest_coord = None
    max_distance = -1

    for coord, tile in visible_tiles.items():
        distance = manhattan_distance(position, coord)
        if distance <= distance_threshold and distance > max_distance and tile.type in ['land', 'menhir'] \
                and distance > 0 and is_safe(tile):
            max_distance = distance
            furthest_coord = coord

    return furthest_coord
