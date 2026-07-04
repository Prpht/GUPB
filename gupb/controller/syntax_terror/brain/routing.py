from gupb.model import characters, coordinates

from ..bfs.core import approach_first_action
from ..combat import handle_enemy_combat
from ..tactics import escape, explore, handle_menhir
from .constants import (
    NUM_ITEM_OUTPUTS,
    OUTPUT_ENEMY_BASE,
    OUTPUT_EXPLORE,
    OUTPUT_MENHIR,
)
from .context import TurnContext


def _handle_item(ctx: TurnContext, idx: int) -> tuple[characters.Action | None, str]:
    item_entries = ctx.memory._turn_extract_snapshot["items"]
    if idx >= len(item_entries):
        return None, "ITEM: None available"
    target_pos = coordinates.Coords(item_entries[idx][1], item_entries[idx][2])
    act = approach_first_action(
        ctx.knowledge.position,
        ctx.facing,
        target_pos,
        target_pos,
        ctx.hp,
        ctx.memory,
        weapon=ctx.weapon,
        omnidirectional=ctx.bfs_omni,
    )
    if act is None:
        return None, f"ITEM -> {target_pos} (BFS pathfinding failed)"
    return act, f"ITEM -> {target_pos}"


def _handle_enemy(
    ctx: TurnContext, enemy_idx: int, value: float
) -> tuple[characters.Action | None, str]:
    player_entries = ctx.memory._turn_extract_snapshot["players"]
    if enemy_idx >= len(player_entries):
        return None, "ENEMY: None available"
    enemy_pos = coordinates.Coords(
        player_entries[enemy_idx][3], player_entries[enemy_idx][4]
    )
    fallback_msg = ""
    if value < 0:
        act = escape(ctx.memory, ctx.knowledge.position, ctx.facing, enemy_pos)
        if act is not None:
            return act, f"ESCAPE from {enemy_pos}"
        fallback_msg = " (ESCAPE failed: no safe tile)"

    enemy_tile = ctx.memory.map_data.get(enemy_pos)
    if not enemy_tile or not enemy_tile.character:
        return None, f"ENEMY {enemy_pos}: Lost sight" + fallback_msg

    opp = enemy_tile.character
    action, msg = handle_enemy_combat(
        ctx.memory,
        ctx.knowledge.position,
        ctx.facing,
        ctx.hp,
        ctx.weapon,
        enemy_pos,
        opp.facing,
        opp.health,
        opp.weapon.name,
    )
    if action is None:
        return None, f"{msg} returned None" + fallback_msg
    return action, msg + fallback_msg


def execute_decision(
    ctx: TurnContext, best_idx: int, value: float
) -> tuple[characters.Action | None, str]:
    if best_idx < NUM_ITEM_OUTPUTS:
        action, msg = _handle_item(ctx, best_idx)
    elif best_idx == OUTPUT_MENHIR:
        action, msg = handle_menhir(ctx.memory, ctx.knowledge.position, ctx.facing)
    elif best_idx == OUTPUT_EXPLORE:
        action, msg = explore(ctx.memory, ctx.knowledge.position, ctx.facing, ctx.hp)
    else:
        action, msg = _handle_enemy(ctx, best_idx - OUTPUT_ENEMY_BASE, value)

    return action, msg
