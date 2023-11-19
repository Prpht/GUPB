from gupb.model import characters
from gupb.model.coordinates import Coords


LARGEST_ARENA_SHAPE = (100, 100)
MAX_STEPS_EXPLORING = 250

# Non walking tiles are: [0, 2, 3]
tiles_mapping = {
    "out": 0,
    "land": 1,
    "sea": 2,
    "wall": 3,
    "menhir": 4,
    "champion": 5,
    "knife": 6,
    "sword": 7,
    "bow_unloaded": 8,
    "bow_loaded": 8, # "bow_unloaded" and "bow_loaded" are the same tile
    "axe": 9,
    "amulet": 10,
    "potion": 11,
    "enymy": 12,
    "mist": 13,
}

weapon_translate = {
    6: "knife",
    7: "sword",
    8: "bow",
    9: "axe",
    10: "amulet",
}

items_ranking = {
    'potion': 0, # 'potion' is not a weapon, but it is the most important item
    'axe': 1,
    'sword': 2,
    'amulet': 3,
    'knife': 4,
    'bow': 5,
    'bow_loaded': 5,
    'bow_unloaded': 5
}

update_facing_right = {
    characters.Facing.UP: characters.Facing.RIGHT,
    characters.Facing.RIGHT: characters.Facing.DOWN,
    characters.Facing.DOWN: characters.Facing.LEFT,
    characters.Facing.LEFT: characters.Facing.UP,
}

update_facing_left = {
    characters.Facing.UP: characters.Facing.LEFT,
    characters.Facing.RIGHT: characters.Facing.UP,
    characters.Facing.DOWN: characters.Facing.RIGHT,
    characters.Facing.LEFT: characters.Facing.DOWN,
}

def manhataan_distance(a: Coords, b: Coords) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
