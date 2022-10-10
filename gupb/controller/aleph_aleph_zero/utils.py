from gupb.model import coordinates, characters
from gupb.model.coordinates import add_coords


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
    if weapon.name == "bow_unloaded":
        return True
    attacked_positions = []
    if weapon.name == "knife":
        attacked_positions.append(knowledge.position + knowledge.visible_tiles[knowledge.position].character.facing.value)
    if weapon.name == "sword" or weapon.name == "axe":
        attacked_positions.append(knowledge.position + knowledge.visible_tiles[knowledge.position].character.facing.value)
        for i in range(2):
            attacked_positions.append(attacked_positions[-1]+ knowledge.visible_tiles[knowledge.position].character.facing.value)
    if weapon.name == "bow_loaded":
        attacked_positions.append(knowledge.position + knowledge.visible_tiles[knowledge.position].character.facing.value)
        for i in range(49):
            attacked_positions.append(attacked_positions[-1]+ knowledge.visible_tiles[knowledge.position].character.facing.value)
    #print(attacked_positions)
    for position in attacked_positions:
        if position in knowledge.visible_tiles:
            if knowledge.visible_tiles[position].character is not None:
                return True
    return False