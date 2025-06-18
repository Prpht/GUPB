from gupb.model import coordinates
from gupb.model import weapons


# -----------------------------------
# Helper functions - distance metrics
# -----------------------------------

# Manhattan distance metric
def manhattan_dist(coord1: coordinates.Coords, coord2: coordinates.Coords) -> int:
    return abs(coord1[0] - coord2[0]) + abs(coord1[1] - coord2[1])

# Maximum (chebyshev) metric
def max_dist(coord1: coordinates.Coords, coord2: coordinates.Coords) -> int:
    return max(abs(coord1[0] - coord2[0]), abs(coord1[1] - coord2[1]))


# ------------------------------------
# Helper functions - weapon properties
# ------------------------------------

# Returns a full weapon instance based on the weapon name
def get_weapon(weapon_name: str) -> weapons.Weapon:
    weapon_map = {
        "knife": weapons.Knife,
        "bow": weapons.Bow,
        "bow_unloaded": weapons.Bow,
        "bow_loaded": weapons.Bow,
        "sword": weapons.Sword,
        "axe": weapons.Axe,
        "amulet": weapons.Amulet,
        "scroll": weapons.Scroll,
    }

    return weapon_map[weapon_name]()