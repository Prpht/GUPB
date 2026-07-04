from gupb.model import characters, coordinates

from ..bfs.core import approach_first_action, _ENEMY_APPROACH_VIS_MAX_COST
from ..bfs.turn_nav import TurnNavigation
from ..memory import MapMemory
from .arena import build_combat_arena
from .firing import firing_positions
from .state import CombatPlayer, CombatState
from .strategies import FastMinimaxStrategy


_STRATEGY = FastMinimaxStrategy(time_limit=0.1)


def _build_state(
    memory: MapMemory,
    my_pos: coordinates.Coords,
    my_facing: characters.Facing,
    my_hp: int,
    my_weapon: str,
    opp_pos: coordinates.Coords,
    opp_facing: characters.Facing,
    opp_hp: int,
    opp_weapon: str,
) -> CombatState:
    arena = build_combat_arena(memory, my_pos, opp_pos)
    me = CombatPlayer(pos=my_pos, facing=my_facing, hp=my_hp, weapon=my_weapon)
    opp = CombatPlayer(pos=opp_pos, facing=opp_facing, hp=opp_hp, weapon=opp_weapon)
    return CombatState(
        me=me,
        opp=opp,
        arena=arena,
        me_to_move=True,
        plies=0,
        alive_count=memory.alive_count,
        menhir_pos=memory.mist_info.menhir_pos,
        mist_radius=memory.mist_radius,
        mist_tick_counter=memory.mist_tick_counter,
        potions=arena.potions,
        loot=arena.loot,
        mist_seen=memory.mist_seen,
    )


def _format_weapon(weapon: str, memory: MapMemory, is_opp: bool) -> str:
    if weapon == "scroll":
        return f"scroll_{5 if is_opp else memory.my_scroll_charges}"
    return weapon


def decide_combat_action(
    memory: MapMemory,
    my_pos: coordinates.Coords,
    my_facing: characters.Facing,
    my_hp: int,
    my_weapon: str,
    opp_pos: coordinates.Coords,
    opp_facing: characters.Facing,
    opp_hp: int,
    opp_weapon: str,
) -> characters.Action | None:
    my_weapon = _format_weapon(my_weapon, memory, False)
    opp_weapon = _format_weapon(opp_weapon, memory, True)
    state = _build_state(
        memory,
        my_pos,
        my_facing,
        my_hp,
        my_weapon,
        opp_pos,
        opp_facing,
        opp_hp,
        opp_weapon,
    )
    return _STRATEGY.search(state)


def _turn_to_valid_firing_facing(
    start: coordinates.Coords,
    start_facing: characters.Facing,
    target: coordinates.Coords,
    my_weapon: str,
    memory: MapMemory,
) -> characters.Action | None:
    from .firing import firing_states
    valid_facings = [
        facing for pos, facing in firing_states(target, my_weapon, memory.map_data, memory)
        if pos == start
    ]
    if not valid_facings:
        return None

    def turn_distance(f1: characters.Facing, f2: characters.Facing) -> int:
        if f1 == f2:
            return 0
        if f1.turn_left() == f2 or f1.turn_right() == f2:
            return 1
        return 2

    best_facing = min(valid_facings, key=lambda f: turn_distance(start_facing, f))
    if start_facing == best_facing:
        return None
    if start_facing.turn_left() == best_facing or start_facing.opposite() == best_facing:
        return characters.Action.TURN_LEFT
    return characters.Action.TURN_RIGHT


def first_action_towards_range_of_target(
    start: coordinates.Coords,
    start_facing: characters.Facing,
    target: coordinates.Coords,
    my_weapon: str,
    memory: MapMemory,
    self_hp: int,
) -> characters.Action | None:
    turn_nav = TurnNavigation.get(memory)
    # Only consider firing positions we can actually walk to (forward-reachable).
    # Ranking by nav_score (return cost) alone could pick a spot that is
    # return-cheap but forward-unreachable (e.g. across a wall), which makes the
    # approach return None and the bot spin in place. Among reachable spots we
    # still prefer the one with the best return cost, breaking ties by how
    # quickly we get there.
    candidates = []
    for pos in firing_positions(target, my_weapon, memory.map_data, memory):
        forward_cost = turn_nav.forward.get(pos)
        if forward_cost is None or forward_cost >= 999999:
            continue
        score = turn_nav.nav_score(pos)
        if score >= 999999:
            continue
        candidates.append((score, forward_cost, pos))

    if not candidates:
        return None

    goal_pos = min(candidates)[2]
    if goal_pos == start:
        act = _turn_to_valid_firing_facing(start, start_facing, target, my_weapon, memory)
        if act is not None:
            return act

    start_tile = memory.map_data.get(start)
    is_omni = my_weapon == "amulet" or (start_tile is not None and any(e.type in ("mist", "fire") for e in start_tile.effects))
    return approach_first_action(
        start,
        start_facing,
        target,
        goal_pos,
        self_hp,
        memory,
        weapon=my_weapon,
        ignored_enemy_pos=target,
        omnidirectional=bool(is_omni),
        vis_max_cost=_ENEMY_APPROACH_VIS_MAX_COST,
    )


_ADJACENT_DELTAS: tuple[tuple[int, int], ...] = (
    (0, 0),
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
)


def _within_one_step(
    point: coordinates.Coords,
    positions: set[coordinates.Coords],
) -> bool:
    if not positions:
        return False
    for dx, dy in _ADJACENT_DELTAS:
        if coordinates.Coords(point[0] + dx, point[1] + dy) in positions:
            return True
    return False


def _should_engage_combat(
    my_pos: coordinates.Coords,
    my_facing: characters.Facing,
    my_weapon: str,
    enemy_pos: coordinates.Coords,
    opp_weapon: str,
    memory: MapMemory,
) -> bool:
    from .arena import _attack_cells

    arena = build_combat_arena(memory, my_pos, enemy_pos)
    opp_attack = set()
    for facing in characters.Facing:
        opp_attack.update(_attack_cells(opp_weapon, enemy_pos, facing, arena))
    if _within_one_step(my_pos, opp_attack):
        return True
    my_attack = set(_attack_cells(my_weapon, my_pos, my_facing, arena))
    return enemy_pos in my_attack


def handle_enemy_combat(
    memory: MapMemory,
    my_pos: coordinates.Coords,
    my_facing: characters.Facing,
    my_hp: int,
    my_weapon: str,
    enemy_pos: coordinates.Coords,
    opp_facing: characters.Facing,
    opp_hp: int,
    opp_weapon: str,
) -> tuple[characters.Action | None, str]:
    my_weapon = _format_weapon(my_weapon, memory, False)
    opp_weapon = _format_weapon(opp_weapon, memory, True)

    if not _should_engage_combat(
        my_pos, my_facing, my_weapon, enemy_pos, opp_weapon, memory
    ):
        act = first_action_towards_range_of_target(
            my_pos, my_facing, enemy_pos, my_weapon, memory, my_hp
        )
        return act, f"APPROACH enemy {enemy_pos}"

    act = decide_combat_action(
        memory,
        my_pos,
        my_facing,
        my_hp,
        my_weapon,
        enemy_pos,
        opp_facing,
        opp_hp,
        opp_weapon,
    )
    if act is None:
        act = first_action_towards_range_of_target(
            my_pos, my_facing, enemy_pos, my_weapon, memory, my_hp
        )
        return act, f"APPROACH (Combat None) {enemy_pos}"
    return act, f"COMBAT {enemy_pos} -> {str(act).split('.')[-1]}"
