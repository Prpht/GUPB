import heapq
import itertools
import math

from gupb.model import characters, coordinates, tiles
from ..memory import MapMemory

from .constants import (
    State,
    FACINGS,
    _TURN_COST,
    _STEP_BASE_COST,
    _INF,
    _FORWARD_ONLY,
    _OMNI_STEPS,
)
from .helpers import is_walkable_tile, forward_pos, _move_facing, first_step_to_cell
from .damage import _step_hp_loss, _enemy_attack_cells, _enemy_range_penalty
from .cache import DistanceMap
from ..utils.visibility import (
    build_target_visibility_cache,
    static_map_fingerprint,
    uses_prescience_vision,
)

_APPROACH_VIS_MAX_COST = 25
# Enemy approaches keep the target in view much longer (combat needs line of
# sight), so they use a higher LOS-aware search cap than item pickups.
_ENEMY_APPROACH_VIS_MAX_COST = 120


def compute_state_distance_map(
    start: coordinates.Coords,
    start_facing: characters.Facing,
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    omnidirectional: bool = False,
    self_hp: int = 8,
    memory: MapMemory | None = None,
    account_hp_loss: bool = True,
    ignored_enemy_pos: coordinates.Coords | None = None,
    force_visible_target: coordinates.Coords | None = None,
    heuristic_target: coordinates.Coords | None = None,
    target_to_stop: coordinates.Coords | None = None,
    use_prescience_vision: bool = False,
    visibility_step_penalty: int = 4,
    early_stop_at_target: bool = False,
    max_search_cost: int | None = None,
) -> tuple[dict[State, int], dict[State, State], dict[State, characters.Action]]:
    start_state: State = (start, start_facing)
    start_cost = 0
    distances = DistanceMap({start_state: start_cost})
    times: dict[State, int] = {start_state: 0}
    hp_lost: dict[State, int] = {start_state: 0}
    previous: dict[State, State] = {}
    action_to_state: dict[State, characters.Action] = {}

    if heuristic_target is not None:
        hx, hy = heuristic_target[0], heuristic_target[1]

        def _state_heuristic(state: State) -> int:
            pos = state[0]
            return abs(pos[0] - hx) + abs(pos[1] - hy)
    else:

        def _state_heuristic(state: State) -> int:
            return 0

    _hp_penalty_table = [
        int(100.0 * (math.exp(4.0 * hp / max(1, self_hp)) - 1.0))
        for hp in range(self_hp + 1)
    ]

    def get_penalty(hp: int) -> int:
        if hp <= 0:
            return 0
        if hp >= len(_hp_penalty_table):
            return _hp_penalty_table[-1]
        return _hp_penalty_table[hp]

    counter = itertools.count()
    start_queue_cost = start_cost + _state_heuristic(start_state)
    queue: list[tuple[int, int, int, int, State]] = [
        (start_queue_cost, start_cost, 0, next(counter), start_state)
    ]
    step_options = _OMNI_STEPS if omnidirectional else _FORWARD_ONLY
    mist_info = memory.mist_info if account_hp_loss and memory else None
    self_pos = start
    attacked_cells = (
        _enemy_attack_cells(self_pos, known_map, ignored_enemy_pos)
        if account_hp_loss
        else {}
    )

    if force_visible_target is not None:
        prescience = use_prescience_vision
        fingerprint = static_map_fingerprint(known_map)
        if memory is not None:
            cache_ticket = (prescience, fingerprint, force_visible_target)
            if memory._target_vis_cache_ticket != cache_ticket:
                memory._target_vis_cache = build_target_visibility_cache(
                    known_map,
                    force_visible_target,
                    use_prescience=prescience,
                )
                memory._target_vis_cache_ticket = cache_ticket
            vis_cache = memory._target_vis_cache
        else:
            vis_cache = build_target_visibility_cache(
                known_map,
                force_visible_target,
                use_prescience=prescience,
            )
        approach_target = force_visible_target
    else:
        vis_cache = None
        approach_target = None

    # Cumulative path cost *including* visibility penalties. Earlier this stored
    # a penalty-free cost, which made the LOS penalty non-cumulative (only the
    # final transition counted), so the planner had no incentive to keep the
    # target in view along an approach. Accumulating the penalty makes a path
    # that watches the target for more steps genuinely cheaper to the goal.
    raw_distances: dict[State, int] = {start_state: start_cost}
    best_goal_cost = _INF
    goal_pos = target_to_stop if early_stop_at_target else None

    while queue:
        queue_cost, current_cost, current_time, _, state = heapq.heappop(queue)
        if current_cost > distances.get(state, _INF):
            continue
        if max_search_cost is not None and current_cost > max_search_cost:
            continue

        if goal_pos is not None and state[0] == goal_pos:
            if current_cost < best_goal_cost:
                best_goal_cost = current_cost
            if (
                early_stop_at_target
                and best_goal_cost < _INF
                and queue
                and queue[0][0] >= best_goal_cost + visibility_step_penalty
            ):
                break

        pos, facing = state
        curr_hp_lost = hp_lost.get(state, 0)
        tile = known_map.get(pos)

        for new_facing, turn_action in (
            (facing.turn_left(), characters.Action.TURN_LEFT),
            (facing.turn_right(), characters.Action.TURN_RIGHT),
        ):
            new_state: State = (pos, new_facing)
            new_time = current_time + 1

            if account_hp_loss and tile is not None:
                turn_hp = _step_hp_loss(
                    pos, tile, new_time, mist_info, attacked_cells, self_hp, self_pos
                )
                total_hp_lost = curr_hp_lost + turn_hp
                if total_hp_lost >= self_hp:
                    continue
                turn_penalty = get_penalty(total_hp_lost) - get_penalty(curr_hp_lost)
                raw_new_cost = raw_distances.get(state, current_cost) + _TURN_COST + turn_penalty
                next_hp_lost = total_hp_lost
            else:
                raw_new_cost = raw_distances.get(state, current_cost) + _TURN_COST
                next_hp_lost = curr_hp_lost
            new_cost = raw_new_cost
            if vis_cache is not None:
                if not vis_cache.can_see(pos, new_facing, approach_target):
                    new_cost += visibility_step_penalty
            if max_search_cost is not None and new_cost > max_search_cost:
                continue
            if new_cost < distances.get(new_state, _INF):
                distances[new_state] = new_cost
                raw_distances[new_state] = new_cost
                times[new_state] = new_time
                hp_lost[new_state] = next_hp_lost
                previous[new_state] = state
                action_to_state[new_state] = turn_action
                if heuristic_target is not None:
                    queue_cost = new_cost + _state_heuristic(new_state)
                else:
                    queue_cost = new_cost
                heapq.heappush(
                    queue, (queue_cost, new_cost, new_time, next(counter), new_state)
                )

        for action, kind in step_options:
            move_facing = _move_facing(facing, kind)
            nxt_pos = forward_pos(pos, move_facing)
            nxt_tile = known_map.get(nxt_pos)
            if nxt_tile is None or not is_walkable_tile(nxt_tile):
                continue

            if (
                account_hp_loss
                and nxt_tile.character is not None
                and nxt_pos != self_pos
                and nxt_pos != goal_pos
                and memory is not None
            ):
                if memory.last_seen.get(nxt_pos) == memory.game_tick:
                    continue

            new_state = (nxt_pos, facing)
            new_time = current_time + 1

            if account_hp_loss:
                step_hp = _step_hp_loss(
                    nxt_pos,
                    nxt_tile,
                    new_time,
                    mist_info,
                    attacked_cells,
                    self_hp,
                    self_pos,
                )
                total_hp_lost = curr_hp_lost + step_hp
                if total_hp_lost >= self_hp:
                    continue
                step_penalty = get_penalty(total_hp_lost) - get_penalty(curr_hp_lost)
                enemy_pen = _enemy_range_penalty(nxt_pos, attacked_cells, new_time)
                raw_new_cost = (
                    raw_distances.get(state, current_cost)
                    + _STEP_BASE_COST
                    + step_penalty
                    + enemy_pen
                )
                next_hp_lost = total_hp_lost
            else:
                raw_new_cost = raw_distances.get(state, current_cost) + _STEP_BASE_COST
                next_hp_lost = curr_hp_lost
            new_cost = raw_new_cost
            if vis_cache is not None:
                if not vis_cache.can_see(nxt_pos, facing, approach_target):
                    new_cost += visibility_step_penalty

            if max_search_cost is not None and new_cost > max_search_cost:
                continue

            if new_cost < distances.get(new_state, _INF):
                distances[new_state] = new_cost
                raw_distances[new_state] = new_cost
                times[new_state] = new_time
                hp_lost[new_state] = next_hp_lost
                previous[new_state] = state
                action_to_state[new_state] = action
                if heuristic_target is not None:
                    queue_cost = new_cost + _state_heuristic(new_state)
                else:
                    queue_cost = new_cost
                heapq.heappush(
                    queue, (queue_cost, new_cost, new_time, next(counter), new_state)
                )

    distances.times = times
    distances.hp_lost = hp_lost
    return distances, previous, action_to_state


def compute_approach_state_distances(
    start: coordinates.Coords,
    start_facing: characters.Facing,
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    target: coordinates.Coords,
    self_hp: int,
    memory: MapMemory,
    ignored_enemy_pos: coordinates.Coords | None = None,
    weapon: str = "knife",
    stop_target: coordinates.Coords | None = None,
    omnidirectional: bool = False,
) -> tuple[dict[State, int], dict[State, State], dict[State, characters.Action]]:
    from .turn_nav import TurnNavigation

    tile = known_map.get(target)
    if tile is None:
        return DistanceMap(), {}, {}
    if not is_walkable_tile(tile) and tile.character is None:
        return DistanceMap(), {}, {}

    actual_stop_target = stop_target if stop_target is not None else target
    max_search_cost = None
    turn_nav = TurnNavigation.get(memory)
    if turn_nav is not None:
        forward_cost = turn_nav.forward.get(actual_stop_target)
        if forward_cost is None or forward_cost >= 999999:
            return DistanceMap(), {}, {}
        # A LOS-maintaining detour rarely lengthens the path much; bound the
        # state search tightly around the straight-line cost (plus room for a
        # few non-seeing steps at the visibility penalty) so far approaches stay
        # fast.
        max_search_cost = forward_cost + 40

    return compute_state_distance_map(
        start=start,
        start_facing=start_facing,
        known_map=known_map,
        omnidirectional=omnidirectional,
        self_hp=self_hp,
        memory=memory,
        account_hp_loss=True,
        ignored_enemy_pos=ignored_enemy_pos,
        force_visible_target=target,
        heuristic_target=actual_stop_target,
        target_to_stop=actual_stop_target,
        use_prescience_vision=uses_prescience_vision(weapon),
        early_stop_at_target=True,
        max_search_cost=max_search_cost,
    )


def _best_state_for_target(
    target: coordinates.Coords,
    state_distances: dict[State, int],
) -> State | None:
    best_state: State | None = None
    best_cost: int | None = None
    for facing in FACINGS:
        state = (target, facing)
        cost = state_distances.get(state)
        if cost is None:
            continue
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_state = state
    return best_state


def first_action_towards_target(
    start: coordinates.Coords,
    start_facing: characters.Facing,
    target: coordinates.Coords,
    state_distances: dict[State, int],
    previous: dict[State, State],
    action_to_state: dict[State, characters.Action],
    forward_parents: dict[coordinates.Coords, coordinates.Coords] | None = None,
    omnidirectional: bool = False,
) -> characters.Action | None:
    start_state: State = (start, start_facing)
    target_state = _best_state_for_target(target, state_distances)
    if target_state is None:
        if forward_parents is not None:
            return first_step_to_cell(
                forward_parents, start, target, start_facing, omnidirectional
            )
        best_fallback = None
        best_dist = float("inf")
        for state in state_distances:
            pos = state[0]
            dist = abs(pos[0] - target[0]) + abs(pos[1] - target[1])
            if dist < best_dist:
                best_dist = dist
                best_fallback = pos
        if best_fallback is not None and best_fallback != start:
            target_state = _best_state_for_target(best_fallback, state_distances)

    if target_state is None or target_state == start_state:
        return None
    state = target_state
    while True:
        parent = previous.get(state)
        if parent is None:
            return None
        if parent == start_state:
            return action_to_state.get(state)
        state = parent


def approach_first_action(
    start: coordinates.Coords,
    start_facing: characters.Facing,
    target: coordinates.Coords,
    stop_target: coordinates.Coords,
    self_hp: int,
    memory: MapMemory,
    weapon: str = "knife",
    ignored_enemy_pos: coordinates.Coords | None = None,
    omnidirectional: bool = False,
    vis_max_cost: int = _APPROACH_VIS_MAX_COST,
) -> characters.Action | None:
    from .turn_nav import TurnNavigation

    turn_nav = TurnNavigation.get(memory)
    forward_cost = turn_nav.forward.get(stop_target)
    if forward_cost is None or forward_cost >= 999999:
        return None
    if forward_cost <= vis_max_cost:
        state_distances, previous, action_to_state = compute_approach_state_distances(
            start,
            start_facing,
            memory.map_data,
            target,
            self_hp,
            memory,
            ignored_enemy_pos=ignored_enemy_pos,
            weapon=weapon,
            stop_target=stop_target,
            omnidirectional=omnidirectional,
        )
        act = first_action_towards_target(
            start,
            start_facing,
            stop_target,
            state_distances,
            previous,
            action_to_state,
            forward_parents=turn_nav.forward.parents,
            omnidirectional=omnidirectional,
        )
        if act is not None:
            return act
    return first_step_to_cell(
        turn_nav.forward.parents, start, stop_target, start_facing, omnidirectional
    )
