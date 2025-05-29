from gupb.model import effects
from gupb.model import weapons
from gupb.model import characters
from gupb.model import consumables
from gupb.model import coordinates

RANDOM_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.ATTACK,
]


DAMAGE_DICT: dict[str, int] = {
    "mist": effects.MIST_DAMAGE,
    "fire": effects.FIRE_DAMAGE,
    "potion": -consumables.POTION_RESTORED_HP,
    "knife": weapons.Knife.cut_effect().damage,
    "sword": weapons.Sword.cut_effect().damage,
    "bow_loaded": weapons.Bow.cut_effect().damage / 2,
    "bow_unloaded": 0,
    "axe": weapons.Axe.cut_effect().damage,
    "amulet": weapons.Amulet.cut_effect().damage,
    "scroll": effects.FIRE_DAMAGE,
}

_bow_loaded = weapons.Bow()
_bow_loaded.ready = True
_bow_unloaded = weapons.Bow()
_bow_unloaded.ready = False
WEAPON_DICT: dict[str, weapons.Weapon] = {
    "knife": weapons.Knife(),
    "sword": weapons.Sword(),
    "bow_loaded": _bow_loaded,
    "bow_unloaded": _bow_unloaded,
    "axe": weapons.Axe(),
    "amulet": weapons.Amulet(),
    "scroll": weapons.Scroll(),
}

WEAPON_ORDER = ("scroll", "knife", "bow_unloaded", "bow_loaded", "sword", "amulet", "axe")

MENHIR_RADIUS = 8
LANDMARK_RADIUS = 3
EPSILON = 0.4
GAMMA = 0.5
ENEMY_CLEANUP_TIME = 4

LANDMARKS = {
    "archipelago": {
        coordinates.Coords(x=6, y=17),
        coordinates.Coords(x=47, y=3),
        coordinates.Coords(x=5, y=40),
        coordinates.Coords(x=27, y=34),
        coordinates.Coords(x=4, y=2),
        coordinates.Coords(x=35, y=8),
        coordinates.Coords(x=14, y=45),
        coordinates.Coords(x=43, y=13),
    },
    "dungeon": {
        coordinates.Coords(x=6, y=48),
        coordinates.Coords(x=34, y=18),
        coordinates.Coords(x=45, y=39),
        coordinates.Coords(x=48, y=17),
        coordinates.Coords(x=16, y=45),
        coordinates.Coords(x=18, y=33),
        coordinates.Coords(x=4, y=16),
        coordinates.Coords(x=24, y=4),
    },
    "fisher_island": {
        coordinates.Coords(x=15, y=32),
        coordinates.Coords(x=45, y=20),
        coordinates.Coords(x=12, y=2),
        coordinates.Coords(x=36, y=7),
        coordinates.Coords(x=10, y=12),
        coordinates.Coords(x=36, y=44),
        coordinates.Coords(x=27, y=47),
        coordinates.Coords(x=37, y=11),
    },
    "island": {
        coordinates.Coords(x=57, y=87),
        coordinates.Coords(x=10, y=31),
        coordinates.Coords(x=75, y=44),
        coordinates.Coords(x=19, y=52),
        coordinates.Coords(x=56, y=44),
        coordinates.Coords(x=57, y=29),
        coordinates.Coords(x=56, y=61),
        coordinates.Coords(x=10, y=13),
    },
    "isolated_shrine": {
        coordinates.Coords(x=1, y=1),
        coordinates.Coords(x=17, y=14),
        coordinates.Coords(x=9, y=9),
        coordinates.Coords(x=9, y=14),
        coordinates.Coords(x=4, y=1),
    },
    "lone_sanctum": {
        coordinates.Coords(x=6, y=4),
        coordinates.Coords(x=8, y=14),
        coordinates.Coords(x=10, y=11),
        coordinates.Coords(x=14, y=3),
        coordinates.Coords(x=8, y=9),
        coordinates.Coords(x=11, y=1),
        coordinates.Coords(x=8, y=11),
    },
    "ordinary_chaos": {
        coordinates.Coords(x=13, y=8),
        coordinates.Coords(x=1, y=22),
        coordinates.Coords(x=21, y=2),
        coordinates.Coords(x=17, y=20),
        coordinates.Coords(x=5, y=6),
        coordinates.Coords(x=14, y=18),
        coordinates.Coords(x=1, y=10),
        coordinates.Coords(x=18, y=1),
    },
    "wasteland": {
        coordinates.Coords(x=38, y=14),
        coordinates.Coords(x=25, y=34),
        coordinates.Coords(x=1, y=14),
        coordinates.Coords(x=27, y=43),
        coordinates.Coords(x=38, y=1),
        coordinates.Coords(x=9, y=44),
        coordinates.Coords(x=48, y=15),
        coordinates.Coords(x=4, y=48),
    },
}
