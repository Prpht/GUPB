import time
import math
import random

from gupb.model import characters, coordinates

from ..actions import apply_action, STEP_ACTIONS, TURN_ACTIONS
from ..arena import _step_delta, _attack_cells, FACING_DELTA
from ...weapons import attack_damage as _attack_damage, parse_weapon, weapon_to_int
from ..state import CombatPlayer, CombatState, _get_weapon_max_range
from ...utils import is_visible


_INF: float = 1e9
_MIN_INF: float = -1e9

_ATTACK = characters.Action.ATTACK
_STEP_FORWARD = characters.Action.STEP_FORWARD
_STEP_BACKWARD = characters.Action.STEP_BACKWARD
_STEP_LEFT = characters.Action.STEP_LEFT
_STEP_RIGHT = characters.Action.STEP_RIGHT
_TURN_LEFT = characters.Action.TURN_LEFT
_TURN_RIGHT = characters.Action.TURN_RIGHT

_STEP_ACTIONS_LIST = [_STEP_FORWARD, _STEP_BACKWARD, _STEP_LEFT, _STEP_RIGHT]
_ALL_ACTIONS_LIST = [_ATTACK, _STEP_FORWARD, _STEP_BACKWARD, _STEP_LEFT, _STEP_RIGHT, _TURN_LEFT, _TURN_RIGHT]

_FACING_TO_INT = {
    characters.Facing.UP: 0,
    characters.Facing.RIGHT: 1,
    characters.Facing.DOWN: 2,
    characters.Facing.LEFT: 3,
}

def _state_key(state: CombatState) -> tuple:
    me = state.me
    opp = state.opp
    return (
        me.pos[0], me.pos[1], _FACING_TO_INT.get(me.facing, 0), me.hp, weapon_to_int(me.weapon),
        opp.pos[0], opp.pos[1], _FACING_TO_INT.get(opp.facing, 0), opp.hp, weapon_to_int(opp.weapon),
        state.me_to_move,
        len(state.extra_fire),
        state.plies,
    )


def _fast_legal_actions(state: CombatState) -> list:
    actor = state.me if state.me_to_move else state.opp
    target = state.opp if state.me_to_move else state.me
    arena = state.arena

    legal = []

    if actor.weapon == "bow_unloaded":
        legal.append(_ATTACK)
    else:
        blocking = {state.me.pos, state.opp.pos} | state.arena.other_champions
        atk_cells = _attack_cells(actor.weapon, actor.pos, actor.facing, arena, blocking)
        name, charges = parse_weapon(actor.weapon)
        if target.pos in atk_cells or (name == "scroll" and charges > 0):
            legal.append(_ATTACK)

    ax, ay = actor.pos
    tx, ty = target.pos

    for action in _STEP_ACTIONS_LIST:
        delta = _step_delta(actor.facing, action)
        nx, ny = ax + delta[0], ay + delta[1]
        dest = coordinates.Coords(nx, ny)
        if dest != target.pos and arena.in_bounds(dest) and arena.is_walkable(dest):
            legal.append(action)

    legal.append(_TURN_LEFT)
    legal.append(_TURN_RIGHT)

    return legal if legal else [_TURN_LEFT]


def _order_fast(state: CombatState, actions: list, cached_action) -> list:
    if len(actions) <= 1:
        return actions

    actor = state.me if state.me_to_move else state.opp
    opp = state.opp if state.me_to_move else state.me
    ax, ay = actor.pos
    ox, oy = opp.pos
    cur_dist = abs(ax - ox) + abs(ay - oy)

    scores = []
    for action in actions:
        if action is cached_action:
            s = 10000
        elif action is _ATTACK:
            s = 5000
        elif action in (_STEP_FORWARD, _STEP_BACKWARD, _STEP_LEFT, _STEP_RIGHT):
            delta = _step_delta(actor.facing, action)
            nx, ny = ax + delta[0], ay + delta[1]
            s = (cur_dist - (abs(nx - ox) + abs(ny - oy))) * 10
        else:
            new_facing = (
                actor.facing.turn_left()
                if action is _TURN_LEFT
                else actor.facing.turn_right()
            )
            fx, fy = FACING_DELTA[new_facing]
            s = 1 if fx * (ox - ax) + fy * (oy - ay) > 0 else -1
        scores.append(s)

    paired = sorted(zip(scores, range(len(actions))), reverse=True)
    return [actions[i] for _, i in paired]


class SearchTimeout(Exception):
    pass


def _minimax_fast(
    state: CombatState,
    depth: int,
    alpha: float,
    beta: float,
    memo: dict,
    deadline: float,
    counter: list,
) -> float:
    if state.is_terminal or depth == 0:
        return state.evaluate()

    counter[0] += 1
    if counter[0] & 127 == 0:
        if time.monotonic() > deadline:
            raise SearchTimeout()

    key = (_state_key(state), depth)
    if key in memo:
        cached_val, flag, _ = memo[key]
        if flag == 0:
            return cached_val
        elif flag == 1:
            alpha = max(alpha, cached_val)
        elif flag == 2:
            beta = min(beta, cached_val)
        if alpha >= beta:
            return cached_val

    cached_best = None
    if key in memo:
        cached_best = memo[key][2]

    actions = _order_fast(state, _fast_legal_actions(state), cached_best)
    orig_alpha = alpha
    best_action = None

    if state.me_to_move:
        best = _MIN_INF
        for action in actions:
            val = _minimax_fast(apply_action(state, action), depth - 1, alpha, beta, memo, deadline, counter)
            if val > best:
                best = val
                best_action = action
            alpha = max(alpha, best)
            if alpha >= beta:
                break
    else:
        best = _INF
        for action in actions:
            val = _minimax_fast(apply_action(state, action), depth - 1, alpha, beta, memo, deadline, counter)
            if val < best:
                best = val
                best_action = action
            beta = min(beta, best)
            if alpha >= beta:
                break

    if best <= orig_alpha:
        flag = 2
    elif best >= beta:
        flag = 1
    else:
        flag = 0
    memo[key] = (best, flag, best_action)
    return best


def _extract_responses(state: CombatState, our_action: characters.Action, memo: dict, depth: int) -> dict:
    cache = {}
    after_our_move = apply_action(state, our_action)
    if after_our_move.is_terminal:
        return cache

    for opp_action in _fast_legal_actions(after_our_move):
        after_opp = apply_action(after_our_move, opp_action)
        if after_opp.is_terminal:
            continue
        key = (_state_key(after_opp), depth - 2)
        if key in memo:
            cached_val, flag, cached_action = memo[key]
            if cached_action is not None:
                gk = _state_key(after_opp)
                cache[gk] = (cached_action, after_opp, depth - 2)
    return cache


class FastMinimaxStrategy:
    def __init__(self, time_limit: float = 0.1, min_depth: int = 2, max_depth: int = 20):
        self.time_limit = time_limit
        self.min_depth = min_depth
        self.max_depth = max_depth
        self._response_cache: dict = {}
        self._last_memo: dict | None = None

    def search(self, state: CombatState) -> characters.Action | None:
        if state.is_terminal:
            return None

        gk = _state_key(state)
        if gk in self._response_cache:
            cached_action, cached_state, cached_depth = self._response_cache[gk]
            self._response_cache.clear()
            if self._last_memo is not None and cached_depth >= 2:
                new_cache = _extract_responses(cached_state, cached_action, self._last_memo, cached_depth)
                self._response_cache.update(new_cache)
            return cached_action

        deadline = time.monotonic() + self.time_limit
        actions = _fast_legal_actions(state)
        if not actions:
            return None

        best_action = max(
            actions, key=lambda a: apply_action(state, a).evaluate()
        )
        memo = {}
        counter = [0]
        reached_depth = 0

        try:
            for depth in range(self.min_depth, self.max_depth + 1, 2):
                if time.monotonic() >= deadline:
                    raise SearchTimeout()

                ordered = _order_fast(state, list(actions), best_action)
                best_value = _MIN_INF
                depth_best = None

                for action in ordered:
                    if time.monotonic() >= deadline:
                        raise SearchTimeout()
                    val = _minimax_fast(
                        apply_action(state, action),
                        depth - 1,
                        _MIN_INF,
                        _INF,
                        memo,
                        deadline,
                        counter,
                    )
                    if val > best_value:
                        best_value = val
                        depth_best = action

                if depth_best is not None:
                    best_action = depth_best
                    reached_depth = depth

                if best_value >= 90000:
                    break
        except SearchTimeout:
            pass

        self._last_memo = memo
        self._response_cache.clear()
        if reached_depth >= 2:
            self._response_cache.update(
                _extract_responses(state, best_action, memo, reached_depth)
            )

        return best_action
