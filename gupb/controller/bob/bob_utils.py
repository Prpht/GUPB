from gupb.model import coordinates
from gupb.model import characters
from gupb.model import tiles
from collections import deque


def _distance(a: coordinates.Coords, b: coordinates.Coords):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


# Szukamy ścieżki do najbliższego interesującego nas miejsca
def choose_path(knowledge: characters.ChampionKnowledge, tile_type: str):
    pos = knowledge.position
    closest_dist = 10000
    closest_tile = None
    for t_pos, tile_desc in knowledge.visible_tiles.items():
        t_type = tile_desc.type
        # Jeśli interesujące pole
        if t_type == tile_type:
            print("Znalazłem!")
            dist = _distance(knowledge.position, t_pos)
            # Jeśli bliżej
            if dist < closest_dist:
                closest_tile = (t_pos, tile_desc)

    if closest_tile is not None:
        vector = coordinates.sub_coords(pos, closest_tile[0])
        return vector
    return None


# Szukanie miejsca przed sobą
def determine_facing_action(knowledge: characters.ChampionKnowledge, previous_positions: deque) -> characters.Action:
    facing_tile, facing_coords = _get_facing_tile(knowledge)
    ft_type = facing_tile.type
    # Sprawdzamy, czy już byliśmy na tym polu
    was_visited = False
    if facing_coords in previous_positions:
        was_visited = True
    if facing_tile.character is not None:
        return characters.Action.ATTACK
    match ft_type:
        case "sea":
            return characters.Action.TURN_RIGHT if was_visited else characters.Action.TURN_LEFT
        case "land":
            return characters.Action.TURN_LEFT if was_visited else characters.Action.STEP_FORWARD
        case "wall":
            return characters.Action.TURN_RIGHT if was_visited else characters.Action.TURN_LEFT
        case "forest":
            return characters.Action.TURN_LEFT if was_visited else characters.Action.STEP_FORWARD
        case "menhir":
            return characters.Action.STEP_FORWARD


def _get_facing(knowledge: characters.ChampionKnowledge) -> coordinates.Coords:
    facing = knowledge.visible_tiles[knowledge.position].character.facing
    match facing:
        case characters.Facing.UP:
            return coordinates.Coords(0, -1)
        case characters.Facing.DOWN:
            return coordinates.Coords(0, 1)
        case characters.Facing.LEFT:
            return coordinates.Coords(-1, 0)
    return coordinates.Coords(1, 0)


def _get_facing_coords(knowledge: characters.ChampionKnowledge) -> coordinates.Coords:
    facing = _get_facing(knowledge)
    return coordinates.Coords(knowledge.position.x + facing.x, knowledge.position.y + facing.y)


def _get_facing_tile(knowledge: characters.ChampionKnowledge) -> (tiles.TileDescription, coordinates.Coords):
    facing = _get_facing_coords(knowledge)
    return knowledge.visible_tiles.get(facing), facing
