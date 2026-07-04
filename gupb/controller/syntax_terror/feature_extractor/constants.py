_MAX_NEAREST_ITEMS: int = 4
_MAX_NEAREST_PLAYERS: int = 4

_ITEM_WEAPON_DIM: int = 7
_PLAYER_WEAPON_DIM: int = 6
_ITEM_SLOT_DIM: int = _ITEM_WEAPON_DIM + 1 + 2
_PLAYER_SLOT_DIM: int = _PLAYER_WEAPON_DIM + 1 + 3 + 2
_PLAYER_HP_OFFSET: int = _PLAYER_WEAPON_DIM

_ITEM_FEATURE_DIM: int = _MAX_NEAREST_ITEMS * _ITEM_SLOT_DIM
_PLAYER_FEATURE_DIM: int = _MAX_NEAREST_PLAYERS * _PLAYER_SLOT_DIM
_META_FEATURE_DIM: int = 14
FEATURE_DIM: int = _ITEM_FEATURE_DIM + _PLAYER_FEATURE_DIM + _META_FEATURE_DIM

_MAX_ARENA_SIZE: int = 42
_HP_MAX: float = 24.0
_DIST_MAX: float = float(2 * _MAX_ARENA_SIZE)
_DEFAULT_MIST_RADIUS: float = float(int(_MAX_ARENA_SIZE * 2**0.5) + 1)
_ALIVE_COUNT_NORM: float = 13.0


def _normalize_hp(hp: int | float) -> float:
    return min(1.0, max(0.0, float(hp) / _HP_MAX))


def _normalize_distance(distance: int | float) -> float:
    return min(1.0, max(0.0, float(distance) / _DIST_MAX))


def _normalize_cost(cost: int | float | None, unreachable: float = 999999.0) -> float:
    if cost is None or cost >= unreachable:
        return 1.0
    return _normalize_distance(cost)


def item_slot_offset(slot: int) -> int:
    return slot * _ITEM_SLOT_DIM


def player_slot_offset(slot: int) -> int:
    return slot * _PLAYER_SLOT_DIM


def player_slot_base(slot: int) -> int:
    return _ITEM_FEATURE_DIM + player_slot_offset(slot)


def player_hp_index(slot: int) -> int:
    return player_slot_base(slot) + _PLAYER_HP_OFFSET
