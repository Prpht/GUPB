from gupb.model import characters, coordinates

from ..bfs.cell import multi_source_cell_distances
from ..bfs.damage import _enemy_attack_cells
from ..bfs.helpers import first_step_to_cell, is_walkable_tile, _neighbors
from ..bfs.turn_nav import TurnNavigation
from ..memory import MapMemory
from ..mist import is_pos_mist_at
from ..combat.arena import _attack_cells, build_combat_arena
from ..utils.visibility import is_visible, static_los_transparent

_UNREACHABLE = 999999
_FAR = 10**9


def _can_move(my_pos: coordinates.Coords, memory: MapMemory) -> bool:
    for nxt in _neighbors(my_pos):
        tile = memory.map_data.get(nxt)
        if tile is not None and is_walkable_tile(tile) and tile.character is None:
            return True
    return False


def _in_danger_now(
    memory: MapMemory,
    my_pos: coordinates.Coords,
    use_return: bool,
) -> bool:
    tile = memory.map_data.get(my_pos)
    if tile is not None:
        effects = {e.type for e in tile.effects}
        if "fire" in effects or "mist" in effects:
            return True
    return use_return and is_pos_mist_at(memory.mist_info, my_pos, 0)


def escape(
    memory: MapMemory,
    my_pos: coordinates.Coords,
    my_facing: characters.Facing,
    enemy_pos: coordinates.Coords,
) -> characters.Action | None:
    enemy_tile = memory.map_data.get(enemy_pos)
    if not enemy_tile or not enemy_tile.character:
        return None

    turn_nav = TurnNavigation.get(memory)
    if turn_nav is None or my_pos not in turn_nav.forward:
        return None
    forward = turn_nav.forward

    if not _can_move(my_pos, memory):
        return None

    w_name = enemy_tile.character.weapon.name
    arena = build_combat_arena(memory, my_pos, enemy_pos)
    threat_cells = {enemy_pos}
    for facing in (
        characters.Facing.UP,
        characters.Facing.DOWN,
        characters.Facing.LEFT,
        characters.Facing.RIGHT,
    ):
        cells = _attack_cells(w_name, enemy_pos, facing, arena)
        threat_cells.update(cells)

    opp_distances = multi_source_cell_distances(list(threat_cells), memory.map_data)
    transparent_coords = static_los_transparent(memory.map_data)

    use_return = (
        memory.menhir_pos is not None
        and turn_nav.return_map is not None
        and turn_nav.nav_score(my_pos) < _UNREACHABLE
    )
    other_enemies_attack = _enemy_attack_cells(my_pos, memory.map_data, ignored_enemy_pos=enemy_pos)
    under_attack = my_pos in threat_cells or my_pos in other_enemies_attack
    in_danger = _in_danger_now(memory, my_pos, use_return) or under_attack

    best_key: tuple[bool, bool, int, int, bool] | None = None
    best_target: coordinates.Coords | None = None
    for cell in forward:
        if in_danger and cell == my_pos:
            continue
        if use_return:
            cost = turn_nav.nav_score(cell)
        else:
            cost = forward[cell]
        if cost >= _UNREACHABLE:
            continue

        enemy_dist = opp_distances.get(cell, _FAR)
        sees_enemy = is_visible(
            cell,
            characters.Facing.UP,
            enemy_pos,
            transparent_coords,
            omnidirectional=True,
        )
        
        cell_takes_damage = (
            forward.hp_lost.get(cell, 0) > 0 
            or cell in threat_cells 
            or cell in other_enemies_attack
        )
        
        key = (cell_takes_damage, -enemy_dist, cost, sees_enemy, cell == my_pos)
        if best_key is None or key < best_key:
            best_key = key
            best_target = cell

    if best_target is None or best_target == my_pos:
        if best_target == my_pos:
            from gupb.model.characters import PENALISED_IDLE_TIME
            idle_limit = max(1, PENALISED_IDLE_TIME - 4)
            if memory.idle_counter >= idle_limit:
                from .anti_idle import get_anti_idle_turn_preferring_enemy
                return get_anti_idle_turn_preferring_enemy(my_pos, my_facing, enemy_pos, transparent_coords)
            return characters.Action.DO_NOTHING
        return None

    is_omni = memory.my_weapon == "amulet" or in_danger
    return first_step_to_cell(
        forward.parents, my_pos, best_target, my_facing, omnidirectional=is_omni
    )
