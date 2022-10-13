import os

from gupb.model import coordinates, characters, tiles
from gupb.model.arenas import TILE_ENCODING, WEAPON_ENCODING, FIXED_MENHIRS
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import add_coords, Coords
from gupb.model.tiles import TileDescription


def taxicab_distance(pos1, pos2):
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])


def neighbours(tile_coords, knowledge):
    neighbours = list()
    for facing in characters.Facing:
        neighbour_coord = add_coords(tile_coords, facing.value)
        if neighbour_coord in knowledge.visible_tiles.keys():
            neighbours.append(neighbour_coord)
    return neighbours


def get_edge_of_vision(knowledge):
    edge_of_vision = set()
    for coord in knowledge.visible_tiles:
        if len(neighbours(coord, knowledge)) < 4:
            edge_of_vision.add(coord)

    return edge_of_vision

def if_character_to_kill(knowledge):
    weapon = knowledge.visible_tiles[knowledge.position].character.weapon
    facing = knowledge.visible_tiles[knowledge.position].character.facing.value
    if weapon.name == "bow_unloaded":
        return True
    attacked_positions = []
    if weapon.name == "knife":
        attacked_positions.append(knowledge.position + facing)
    if weapon.name == "sword":
        attacked_positions.append(knowledge.position + facing)
        for i in range(2):
            attacked_positions.append(attacked_positions[-1]+ facing)
    if weapon.name == "bow_loaded":
        attacked_positions.append(knowledge.position + facing)
        for i in range(49):
            attacked_positions.append(attacked_positions[-1]+ facing)
    if weapon.name == "axe":
        attacked_positions.append(knowledge.position + facing)
        last_pos = attacked_positions[-1]
        if facing.x == 0:
            for cord in [Coords(-1,0), Coords(1,0),]:
                attacked_positions.append(last_pos + cord)
        else:
            for cord in [Coords(0,-1), Coords(0,1)]:
                attacked_positions.append(last_pos + cord)

    for position in attacked_positions:
        if position in knowledge.visible_tiles:
            if knowledge.visible_tiles[position].character is not None:
                return True
    return False

def get_knowledge_from_file(map_name):
    arena_file_path = os.path.join('resources', 'arenas', f'{map_name}.gupb')

    with open(arena_file_path, "r") as file:
        lines = file.readlines()

    list_lines = [[letter for letter in line if letter!='\n'] for line in lines]
    vis_tiles = dict()

    for y, line in enumerate(list_lines):
        for x, character in enumerate(line):
            position = coordinates.Coords(x,y)
            if character in TILE_ENCODING:
                vis_tiles[position] = TILE_ENCODING[character]().description()
            elif character in WEAPON_ENCODING:
                vis_tiles[position] = TileDescription(
                    "land",
                    WEAPON_ENCODING[character]().description(),
                    None,
                    []
                )

    if map_name in FIXED_MENHIRS.keys():
        vis_tiles[FIXED_MENHIRS[map_name]] = tiles.Menhir().description()
    return ChampionKnowledge(None, 0, visible_tiles=vis_tiles)

