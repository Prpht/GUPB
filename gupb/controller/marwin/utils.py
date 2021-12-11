from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
from collections import defaultdict
from gupb import model
from gupb.model import characters, tiles, coordinates, weapons
from typing import Dict, List


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.DO_NOTHING,
]

KNIFE = 'knife'
AXE = 'axe'
BOW_UNLOADED = 'bow_unloaded'
BOW_LOADED = 'bow_loaded'
AMULET = 'amulet'
SWORD = 'sword'
BOW = 'bow'

WEAPONS_ORDER = {
    KNIFE: 0,
    BOW_UNLOADED: 4,
    BOW_LOADED: 4,
    AXE: 5,
    AMULET: 2,
    SWORD: 3,
}

BLOCKERS = ["=", "#"]
ARENA_SIZE = (50, 50)

# states
TURN_AROUND = 'turn_around'
GOING_FOR_WEAPON = 'going_for_weapon'
GOING_TO_MENHIR = 'going_to_menhir'
GOING_TO_TURN = 'going_to_turn'
CAMPING = 'camping'

# weights during pathfinding
W_UNDISCOVERED = 0
W_BLOCKERS = -1
W_PASSAGE = 1
W_TAKEN_WEAPON = 10
W_MIST = 50

# arena objects
WALL = 'wall'
SEA = 'sea'
PASSAGE = 'land'
TURN = 'turn'
ENEMY = 'enemy'
MENHIR = 'menhir'
WEAPON = 'weapon'
MIST = 'mist'


def find_path_to_target(arena, start: coordinates.Coords, end: coordinates.Coords):
    grid = Grid(matrix=arena)
    start_node = grid.node(start.x, start.y)
    end_node = grid.node(end.x, end.y)
    finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
    path, runs = finder.find_path(start_node, end_node, grid)
    return path


def is_tile_transparent(tile_name: str) -> bool:
    from gupb.model import tiles
    tiles_cls = {
        'wall': tiles.Wall,
        'sea': tiles.Sea,
        'land': tiles.Land,
        'menhir': tiles.Menhir
    }

    for key, tile_cls in tiles_cls.items():
        if key in tile_name.lower():
            return tile_cls.terrain_transparent()
    return True


def get_cut_positions(weapon_cls: str, terrain: Dict[coordinates.Coords, tiles.TileDescription],
                      position: coordinates.Coords, facing: characters.Facing) -> List[coordinates.Coords]:
    cut_positions = []
    cut_position = position
    for _ in range(weapon_cls.reach()):
        cut_position += facing.value
        if cut_position not in terrain:
            break
        cut_positions.append(cut_position)
        if not is_tile_transparent(terrain[cut_position].type):
            break
    return cut_positions


def get_weapon_for_description(weapon_description: str) -> model.weapons.Weapon:
    # from gupb.model import weapons

    weapons_cls = {
        KNIFE: model.weapons.Knife,
        SWORD: model.weapons.Sword,
        BOW: model.weapons.Bow,
        AXE: model.weapons.Axe,
        AMULET: model.weapons.Amulet
    }
    for key, weapon in weapons_cls.items():
        if key in weapon_description.lower():
            return weapon
    return None


def scan_terrain(terrain: Dict[coordinates.Coords, tiles.TileDescription], character_facing: characters.Facing,
                map_matrix, character_position: coordinates.Coords) -> Dict[str, List[coordinates.Coords]]:
    unpassable = {WALL, SEA}
    result = defaultdict(list)
    for coords, tile in terrain.items():
        if tile.character is not None:
            result[ENEMY].append(coords)
        if map_matrix[coords[1], coords[0]] == W_UNDISCOVERED:
            result[tile.type].append(coords)
            if tile.loot is not None:
                result[WEAPON].append((coords, tile.loot.name))
        if tile.type not in unpassable and MIST in tile.effects:
            result[MIST].append(coords)
        if _is_turn(character_facing, character_position, coords, tile, unpassable):
            result[TURN].append(coords)
    return result


def _is_turn(character_facing: characters.Facing, character_position: coordinates.Coords,
            coords, tile: tiles.TileDescription, unpassable) -> bool:
    if tile.type in unpassable:
        return False
    if character_facing in (characters.Facing.LEFT, characters.Facing.RIGHT):
        return character_position.y != coords[1]
    else:
        return character_position.x != coords[0]


def able_to_attack(enemies: List[coordinates.Coords], sight_area: Dict[coordinates.Coords, tiles.TileDescription],
            character_position: coordinates.Coords, facing: characters.Facing, weapon: weapons.WeaponDescription) -> bool:
    weapon_cls = get_weapon_for_description(weapon.name)
    return are_enemies_in_reach(enemies, weapon_cls, sight_area, character_position, facing)


def are_enemies_in_reach(enemies, weapon_cls, sight_area, position, facing):
    weapon_reach = _get_cut_positions(weapon_cls, sight_area, position, facing)
    for enemy in enemies:
        if enemy in weapon_reach:
            return True


def _get_cut_positions(weapon_cls, sight_area, position, facing):
    try:
        weapon_reach = weapon_cls.cut_positions(sight_area, position, facing)
    except AttributeError:
        weapon_reach = get_cut_positions(weapon_cls, sight_area, position, facing)
    return weapon_reach


def get_distance(coords_a, coords_b):
    return ((coords_a[0] - coords_b[0]) ** 2 + (coords_a[1] - coords_b[1]) ** 2) ** 0.5