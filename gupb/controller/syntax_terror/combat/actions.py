from gupb.model import characters, coordinates, effects
from gupb.model.consumables import POTION_RESTORED_HP

from ..mist import is_pos_mist_at
from ..weapons import attack_damage as _attack_damage, parse_weapon
from .arena import CombatArena, _attack_cells, _step_delta
from .state import CombatPlayer, CombatState

_NON_DROPPABLE_WEAPONS: frozenset[str] = frozenset({"knife", "scroll"})


STEP_ACTIONS: frozenset[characters.Action] = frozenset({
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
})
TURN_ACTIONS: frozenset[characters.Action] = frozenset({
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
})

_STEP_ACTIONS_ID_SET = frozenset(id(a) for a in STEP_ACTIONS)
_TURN_ACTIONS_ID_SET = frozenset(id(a) for a in TURN_ACTIONS)



def _apply_tile_damage(player: CombatPlayer, state: CombatState, extra_fire: tuple[coordinates.Coords, ...]) -> CombatPlayer:
    damage = 0
    arena_fire_count = next((p[1] for p in state.arena.fire if p[0] == player.pos), 0)
    extra_fire_count = extra_fire.count(player.pos)
    total_fire = arena_fire_count + extra_fire_count
    if total_fire > 0:
        damage += total_fire * effects.FIRE_DAMAGE

    ticks_ahead = state.plies // 2
    if is_pos_mist_at(state, player.pos, ticks_ahead):
        damage += effects.MIST_DAMAGE

    damage += state.arena.threat_map.get(player.pos, 0)

    if damage == 0:
        return player
    return CombatPlayer(
        player.pos, player.facing, max(0, player.hp - damage), player.weapon
    )


def _rotate(actor: CombatPlayer, action: characters.Action) -> CombatPlayer:
    if action == characters.Action.TURN_LEFT:
        return CombatPlayer(actor.pos, actor.facing.turn_left(), actor.hp, actor.weapon)
    return CombatPlayer(actor.pos, actor.facing.turn_right(), actor.hp, actor.weapon)


def _move(
    actor: CombatPlayer, target: CombatPlayer, action: characters.Action, arena: CombatArena
) -> CombatPlayer:
    delta = _step_delta(actor.facing, action)
    new_pos = coordinates.Coords(actor.pos[0] + delta[0], actor.pos[1] + delta[1])
    if new_pos == target.pos:
        return CombatPlayer(actor.pos, actor.facing, max(0, actor.hp - 1), actor.weapon)
    if arena.in_bounds(new_pos):
        if arena.is_walkable(new_pos):
            return CombatPlayer(new_pos, actor.facing, actor.hp, actor.weapon)
        return actor
    if arena.in_bounds(actor.pos):
        penalty = max(1, actor.hp // 2)
        return CombatPlayer(new_pos, actor.facing, max(0, actor.hp - penalty), actor.weapon)
    return CombatPlayer(new_pos, actor.facing, actor.hp, actor.weapon)


def _attack(
    actor: CombatPlayer, target: CombatPlayer, arena: CombatArena, extra_fire: tuple[coordinates.Coords, ...]
) -> tuple[CombatPlayer, CombatPlayer, tuple[coordinates.Coords, ...]]:
    if actor.weapon == "bow_unloaded":
        return (
            CombatPlayer(actor.pos, actor.facing, actor.hp, "bow_loaded"),
            target,
            extra_fire,
        )

    blocking_positions = {actor.pos, target.pos} | arena.other_champions
    cells = _attack_cells(actor.weapon, actor.pos, actor.facing, arena, blocking_positions)
    w_name, charges = parse_weapon(actor.weapon)
    dmg = _attack_damage(actor.weapon)
    if w_name == "scroll" and charges > 0:
        dmg = effects.FIRE_DAMAGE
    new_target = target
    if target.pos in cells:
        new_target = CombatPlayer(
            target.pos,
            target.facing,
            max(0, target.hp - dmg),
            target.weapon,
        )

    new_actor = actor
    new_extra_fire = extra_fire
    if w_name == "bow_loaded":
        new_actor = CombatPlayer(actor.pos, actor.facing, actor.hp, "bow_unloaded")
    elif w_name == "scroll":
        if charges > 0:
            new_extra_fire = extra_fire + tuple(cells)
            new_actor = CombatPlayer(actor.pos, actor.facing, actor.hp, f"scroll_{charges - 1}")
    return new_actor, new_target, new_extra_fire


def _apply_tile_pickup(
    actor: CombatPlayer,
    potions: frozenset[coordinates.Coords],
    loot: tuple[tuple[coordinates.Coords, str], ...],
) -> tuple[CombatPlayer, frozenset[coordinates.Coords], tuple[tuple[coordinates.Coords, str], ...]]:
    new_potions = potions
    new_loot = loot

    if actor.pos in potions:
        healed_hp = actor.hp + POTION_RESTORED_HP
        actor = CombatPlayer(actor.pos, actor.facing, healed_hp, actor.weapon)
        new_potions = potions - {actor.pos}

    for pos, weapon_name in loot:
        if pos == actor.pos:
            old_weapon = actor.weapon
            if weapon_name == "scroll":
                weapon_name = "scroll_5"
            actor = CombatPlayer(actor.pos, actor.facing, actor.hp, weapon_name)
            remaining = [entry for entry in new_loot if entry[0] != pos]
            old_w_name, _ = parse_weapon(old_weapon)
            if old_weapon not in _NON_DROPPABLE_WEAPONS and old_w_name != "scroll":
                remaining.append((pos, old_weapon))
            new_loot = tuple(remaining)
            break

    return actor, new_potions, new_loot


def apply_action(state: CombatState, action: characters.Action) -> CombatState:
    if state.me_to_move:
        actor, target = state.me, state.opp
    else:
        actor, target = state.opp, state.me

    new_actor = actor
    new_target = target
    new_extra_fire = state.extra_fire

    action_id = id(action)

    if action_id in _TURN_ACTIONS_ID_SET:
        new_actor = _rotate(actor, action)
    elif action_id in _STEP_ACTIONS_ID_SET:
        new_actor = _move(actor, target, action, state.arena)
    elif action == characters.Action.ATTACK:
        new_actor, new_target, new_extra_fire = _attack(
            actor, target, state.arena, state.extra_fire
        )

    new_actor = _apply_tile_damage(new_actor, state, new_extra_fire)

    new_potions = state.potions
    new_loot = state.loot
    if action_id in _STEP_ACTIONS_ID_SET and new_actor.pos != actor.pos:
        new_actor, new_potions, new_loot = _apply_tile_pickup(
            new_actor, new_potions, new_loot
        )

    if state.me_to_move:
        new_me, new_opp = new_actor, new_target
    else:
        new_me, new_opp = new_target, new_actor

    return CombatState(
        new_me,
        new_opp,
        state.arena,
        not state.me_to_move,
        state.plies + 1,
        state.alive_count,
        state.menhir_pos,
        state.mist_radius,
        state.mist_tick_counter,
        new_extra_fire,
        new_potions,
        new_loot,
        state.mist_seen,
    )
