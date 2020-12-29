from gupb.model.tiles import Menhir, Wall, Sea, Land
from gupb.model.weapons import Knife, Sword, Bow, Axe, Amulet

FIELD_WEIGHT = 100

TILES = [Land, Sea, Wall, Menhir]

TILES_MAP = {tile().description().type: tile for tile in TILES}

WEAPONS = [(Knife, 100), (Sword, 25), (Bow, 1), (Axe, 10), (Amulet, 25)]
WEAPONS.sort(key=lambda x: x[1])

WEAPONS_MAP = {weapon().description(): weapon for weapon, _ in WEAPONS}

WEAPONS_ENCODING = {weapon().description(): value for weapon, value in WEAPONS}

FIELD_ATTACKED = FIELD_WEIGHT * FIELD_WEIGHT

WEAPONS_PRIORITY = [weapon[0]().description() for weapon in WEAPONS]