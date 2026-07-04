from dataclasses import dataclass, field
import functools
import bresenham

from gupb.model import characters, coordinates, tiles

from ..bfs.constants import LOS_TRANSPARENT_TYPES
from ..bfs.helpers import is_passable_tile_type
from ..memory import MapMemory
from ..weapons import parse_weapon, attack_damage


_FIRE_EFFECT_TYPE: str = "fire"
_MIST_EFFECT_TYPE: str = "mist"


@dataclass(frozen=True)
class CombatArena:
    origin: coordinates.Coords
    size: int
    walkable: frozenset[coordinates.Coords]
    transparent: frozenset[coordinates.Coords]
    fire: frozenset[tuple[coordinates.Coords, int]]
    mist: frozenset[coordinates.Coords]
    potions: frozenset[coordinates.Coords] = frozenset()
    loot: tuple[tuple[coordinates.Coords, str], ...] = ()
    terrain_transparent: frozenset[coordinates.Coords] = frozenset()
    other_champions: frozenset[coordinates.Coords] = frozenset()
    known: frozenset[coordinates.Coords] = frozenset()
    threat_map: dict[coordinates.Coords, int] = field(default_factory=dict, hash=False)

    def in_bounds(self, pos: coordinates.Coords) -> bool:
        return (
            self.origin[0] <= pos[0] < self.origin[0] + self.size
            and self.origin[1] <= pos[1] < self.origin[1] + self.size
        )

    def is_walkable(self, pos: coordinates.Coords) -> bool:
        return pos in self.walkable

    def has_fire(self, pos: coordinates.Coords) -> bool:
        return any(p[0] == pos for p in self.fire)


def _effect_types(tile: tiles.TileDescription) -> set[str]:
    return {effect.type for effect in tile.effects}


def build_combat_arena(
    memory: MapMemory,
    my_pos: coordinates.Coords,
    opp_pos: coordinates.Coords,
    size: int = 100,
) -> CombatArena:
    cache_key = (my_pos, opp_pos, size)
    cached = memory._combat_arena_cache.get(cache_key)
    if cached is not None:
        return cached

    origin = coordinates.Coords(0, 0)

    walkable: set[coordinates.Coords] = set()
    transparent: set[coordinates.Coords] = set()
    terrain_transparent: set[coordinates.Coords] = set()
    fire_list: list[tuple[coordinates.Coords, int]] = []
    mist: set[coordinates.Coords] = set()
    potions: set[coordinates.Coords] = set()
    loot_list: list[tuple[coordinates.Coords, str]] = []

    for pos, tile in memory.map_data.items():
        effect_types = _effect_types(tile)
        fire_count = sum(1 for e in tile.effects if e.type == _FIRE_EFFECT_TYPE)
        if fire_count > 0:
            fire_list.append((pos, fire_count))
        if _MIST_EFFECT_TYPE in effect_types:
            mist.add(pos)
        if is_passable_tile_type(tile.type):
            if not (tile.character is not None and pos != my_pos and pos != opp_pos):
                walkable.add(pos)
        if tile.type in LOS_TRANSPARENT_TYPES:
            terrain_transparent.add(pos)
            if tile.character is None:
                transparent.add(pos)
        if tile.consumable is not None:
            potions.add(pos)
        if tile.loot is not None:
            loot_list.append((pos, tile.loot.name))

    other_champions = (terrain_transparent - transparent) - {my_pos, opp_pos}

    dummy_arena = CombatArena(
        origin=origin,
        size=size,
        walkable=frozenset(walkable),
        transparent=frozenset(transparent),
        fire=frozenset(fire_list),
        mist=frozenset(mist),
        potions=frozenset(potions),
        loot=tuple(loot_list),
        terrain_transparent=frozenset(terrain_transparent),
        other_champions=frozenset(other_champions),
        known=frozenset(memory.map_data.keys()),
        threat_map={},
    )

    third_party_threats_dict: dict[coordinates.Coords, int] = {}
    blocking = {my_pos, opp_pos} | other_champions
    for pos in other_champions:
        tile = memory.map_data.get(pos)
        if tile and tile.character:
            w_name = tile.character.weapon.name
            cells = _attack_cells(w_name, pos, tile.character.facing, dummy_arena, blocking)
            dmg = attack_damage(w_name)
            for cell in cells:
                third_party_threats_dict[cell] = max(third_party_threats_dict.get(cell, 0), dmg)

    arena = CombatArena(
        origin=origin,
        size=size,
        walkable=frozenset(walkable),
        transparent=frozenset(transparent),
        fire=frozenset(fire_list),
        mist=frozenset(mist),
        potions=frozenset(potions),
        loot=tuple(loot_list),
        terrain_transparent=frozenset(terrain_transparent),
        other_champions=frozenset(other_champions),
        known=frozenset(memory.map_data.keys()),
        threat_map=third_party_threats_dict,
    )
    memory._combat_arena_cache[cache_key] = arena
    return arena


_AMULET_DELTAS: tuple[tuple[int, int], ...] = (
    (1, 1),
    (-1, 1),
    (1, -1),
    (-1, -1),
    (2, 2),
    (-2, 2),
    (2, -2),
    (-2, -2),
)

FACING_DELTA = {
    characters.Facing.UP: (0, -1),
    characters.Facing.DOWN: (0, 1),
    characters.Facing.LEFT: (-1, 0),
    characters.Facing.RIGHT: (1, 0),
}

_STEP_DELTA_TABLE = {
    (characters.Facing.UP, characters.Action.STEP_FORWARD): characters.Facing.UP.value,
    (
        characters.Facing.UP,
        characters.Action.STEP_BACKWARD,
    ): characters.Facing.UP.opposite().value,
    (
        characters.Facing.UP,
        characters.Action.STEP_LEFT,
    ): characters.Facing.UP.turn_left().value,
    (
        characters.Facing.UP,
        characters.Action.STEP_RIGHT,
    ): characters.Facing.UP.turn_right().value,
    (
        characters.Facing.DOWN,
        characters.Action.STEP_FORWARD,
    ): characters.Facing.DOWN.value,
    (
        characters.Facing.DOWN,
        characters.Action.STEP_BACKWARD,
    ): characters.Facing.DOWN.opposite().value,
    (
        characters.Facing.DOWN,
        characters.Action.STEP_LEFT,
    ): characters.Facing.DOWN.turn_left().value,
    (
        characters.Facing.DOWN,
        characters.Action.STEP_RIGHT,
    ): characters.Facing.DOWN.turn_right().value,
    (
        characters.Facing.LEFT,
        characters.Action.STEP_FORWARD,
    ): characters.Facing.LEFT.value,
    (
        characters.Facing.LEFT,
        characters.Action.STEP_BACKWARD,
    ): characters.Facing.LEFT.opposite().value,
    (
        characters.Facing.LEFT,
        characters.Action.STEP_LEFT,
    ): characters.Facing.LEFT.turn_left().value,
    (
        characters.Facing.LEFT,
        characters.Action.STEP_RIGHT,
    ): characters.Facing.LEFT.turn_right().value,
    (
        characters.Facing.RIGHT,
        characters.Action.STEP_FORWARD,
    ): characters.Facing.RIGHT.value,
    (
        characters.Facing.RIGHT,
        characters.Action.STEP_BACKWARD,
    ): characters.Facing.RIGHT.opposite().value,
    (
        characters.Facing.RIGHT,
        characters.Action.STEP_LEFT,
    ): characters.Facing.RIGHT.turn_left().value,
    (
        characters.Facing.RIGHT,
        characters.Action.STEP_RIGHT,
    ): characters.Facing.RIGHT.turn_right().value,
}


_FAST_STEP_DELTA_TABLE = {(id(f), id(a)): v for (f, a), v in _STEP_DELTA_TABLE.items()}


def _step_delta(
    facing: characters.Facing, action: characters.Action
) -> coordinates.Coords:
    return _FAST_STEP_DELTA_TABLE.get(
        (id(facing), id(action)), coordinates.Coords(0, 0)
    )


def _line_cells(
    pos: coordinates.Coords,
    facing: characters.Facing,
    reach: int,
    arena: CombatArena,
    blocking_positions=None,
) -> list[coordinates.Coords]:
    out: list[coordinates.Coords] = []
    fx, fy = FACING_DELTA[facing]
    ox, oy = arena.origin[0], arena.origin[1]
    end_x, end_y = ox + arena.size, oy + arena.size
    cx, cy = pos[0], pos[1]
    known = arena.known
    for _ in range(reach):
        cx += fx
        cy += fy
        if not (ox <= cx < end_x and oy <= cy < end_y):
            break
        cur = coordinates.Coords(cx, cy)
        out.append(cur)
        if known is not None:
            if cur in known and cur not in arena.terrain_transparent:
                break
        else:
            if cur not in arena.terrain_transparent:
                break
        if blocking_positions is not None and cur in blocking_positions:
            break
    return out


def _axe_cells(
    pos: coordinates.Coords, facing: characters.Facing
) -> list[coordinates.Coords]:
    fx, fy = FACING_DELTA[facing]
    centre = coordinates.Coords(pos[0] + fx, pos[1] + fy)
    lx, ly = FACING_DELTA[facing.turn_left()]
    rx, ry = FACING_DELTA[facing.turn_right()]
    return [
        coordinates.Coords(centre[0] + lx, centre[1] + ly),
        centre,
        coordinates.Coords(centre[0] + rx, centre[1] + ry),
    ]


def _amulet_cells(pos: coordinates.Coords) -> list[coordinates.Coords]:
    return [coordinates.Coords(pos[0] + dx, pos[1] + dy) for dx, dy in _AMULET_DELTAS]


def _attack_cells(
    weapon: str,
    pos: coordinates.Coords,
    facing: characters.Facing,
    arena: CombatArena,
    blocking_positions=None,
) -> list[coordinates.Coords]:
    name, charges = parse_weapon(weapon)
    if name == "scroll":
        if charges <= 0:
            return []
        return _line_cells(pos, facing, 1, arena, blocking_positions)
    if name == "knife":
        return _line_cells(pos, facing, 1, arena, blocking_positions)
    if name == "sword":
        return _line_cells(pos, facing, 3, arena, blocking_positions)
    if name in ("bow_loaded", "bow_unloaded"):
        return _line_cells(pos, facing, arena.size, arena, blocking_positions)
    if name == "axe":
        return _axe_cells(pos, facing)
    if name == "amulet":
        return _amulet_cells(pos)
    return _line_cells(pos, facing, 1, arena, blocking_positions)
