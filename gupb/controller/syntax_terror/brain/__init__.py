import random
import time

import numpy as np

from gupb.model import characters, coordinates

from ..memory import MapMemory
from ..policy_nn import FeedForwardNetwork, PolicyModel
from .context import (
    TurnContext,
    build_turn_context,
    is_omnidirectional,
    self_facing,
    self_stats,
)
from .constants import OUTPUT_ENEMY_BASE
from .features import extract_features, mask_invalid_outputs, get_available_actions_mask
from .routing import execute_decision

# The engine applies an idle HP penalty once a champion has stayed on the same
# tile *and* facing for PENALISED_IDLE_TIME turns. We force a random turn a few
# turns earlier so the bot never actually takes that damage when it is stuck.
_IDLE_TURN_LIMIT = max(1, characters.PENALISED_IDLE_TIME - 4)
_ANTI_IDLE_TURNS = (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT)


class Brain:
    def __init__(self, net: FeedForwardNetwork):
        self.model = PolicyModel(net)
        self.last_decision_msg = ""
        self.debug = False
        self.last_debug_state: dict | None = None
        self._idle_state: tuple[coordinates.Coords, characters.Facing] | None = None
        self._idle_counter = 0

    def reset(self) -> None:
        self.last_debug_state = None
        self._idle_state = None
        self._idle_counter = 0

    def pick_action(
        self, knowledge: characters.ChampionKnowledge, memory: MapMemory
    ) -> characters.Action | None:
        start_t = time.perf_counter()
        facing = self_facing(knowledge, memory)
        hp, weapon = self_stats(knowledge, memory)
        ctx = build_turn_context(knowledge, memory, facing, hp, weapon)

        features = extract_features(ctx)
        mask = get_available_actions_mask(
            features, ctx.memory, ctx.distances, ctx.knowledge.position
        )
        available_indices = np.where(mask)[0]

        if len(available_indices) == 1:
            only_idx = int(available_indices[0])
            if only_idx < OUTPUT_ENEMY_BASE:
                return self._execute_single_action(
                    ctx, only_idx, features, start_t, facing, knowledge
                )

        return self._choose_action_with_model(ctx, features, start_t, facing, knowledge)

    def _execute_single_action(
        self,
        ctx: TurnContext,
        best_idx: int,
        features: np.ndarray,
        start_t: float,
        facing: characters.Facing,
        knowledge: characters.ChampionKnowledge,
    ) -> characters.Action:
        from .constants import NUM_NN_OUTPUTS, MASK_DISABLED

        action, msg = execute_decision(ctx, best_idx, 1.0)
        action, msg = self._avoid_idle_penalty(action, msg, knowledge.position, facing)
        self.last_decision_msg = msg

        if self.debug:
            episode_time = time.perf_counter() - start_t
            outputs = np.zeros(NUM_NN_OUTPUTS)
            outputs[best_idx] = 1.0
            masked_scores = np.full(NUM_NN_OUTPUTS, MASK_DISABLED)
            masked_scores[best_idx] = 1.0
            self._save_debug_state(
                ctx,
                outputs,
                masked_scores,
                best_idx,
                features,
                facing,
                msg,
                episode_time,
            )
        return action

    def _choose_action_with_model(
        self,
        ctx: TurnContext,
        features: np.ndarray,
        start_t: float,
        facing: characters.Facing,
        knowledge: characters.ChampionKnowledge,
    ) -> characters.Action:
        outputs = self.model.predict(features)
        masked_scores = mask_invalid_outputs(
            outputs, features, ctx.memory, ctx.distances, outputs, ctx.knowledge.position
        )
        from .constants import MASK_DISABLED, OUTPUT_ESCAPE_BASE, OUTPUT_ENEMY_BASE

        sorted_indices = np.argsort(masked_scores)[::-1]
        action = None
        best_idx = int(sorted_indices[0])
        msg_parts = []

        for idx in sorted_indices:
            curr_idx = int(idx)
            if masked_scores[curr_idx] <= MASK_DISABLED:
                break
                
            if curr_idx >= OUTPUT_ESCAPE_BASE:
                enemy_idx = curr_idx - OUTPUT_ESCAPE_BASE
                action, curr_msg = execute_decision(ctx, OUTPUT_ENEMY_BASE + enemy_idx, -1.0)
            else:
                action, curr_msg = execute_decision(ctx, curr_idx, 1.0)
                
            best_idx = curr_idx
            if curr_msg:
                msg_parts.append(curr_msg)
            if action is not None:
                break

        msg = " | ".join(msg_parts)

        action, msg = self._avoid_idle_penalty(action, msg, knowledge.position, facing)
        self.last_decision_msg = msg

        if self.debug:
            episode_time = time.perf_counter() - start_t
            self._save_debug_state(
                ctx,
                outputs,
                masked_scores,
                best_idx,
                features,
                facing,
                msg,
                episode_time,
            )

        return action

    def _avoid_idle_penalty(
        self,
        action: characters.Action | None,
        msg: str,
        position: coordinates.Coords,
        facing: characters.Facing,
    ) -> tuple[characters.Action | None, str]:
        state = (position, facing)
        if state == self._idle_state:
            self._idle_counter += 1
        else:
            self._idle_counter = 0
            self._idle_state = state

        if action is None:
            self._idle_counter = 0
            self._idle_state = None
            from ..tactics.anti_idle import get_random_anti_idle_turn
            turn = get_random_anti_idle_turn()
            return turn, f"{msg} -> ANTI-IDLE {str(turn).split('.')[-1]}"

        if action == characters.Action.DO_NOTHING:
            if self._idle_counter >= _IDLE_TURN_LIMIT:
                self._idle_counter = 0
                self._idle_state = None
                from ..tactics.anti_idle import get_random_anti_idle_turn
                turn = get_random_anti_idle_turn()
                return turn, f"{msg} -> ANTI-IDLE {str(turn).split('.')[-1]}"

        return action, msg

    def _save_debug_state(
        self,
        ctx: TurnContext,
        outputs,
        masked_scores,
        best_idx,
        features,
        facing,
        msg,
        episode_time: float,
    ) -> None:
        from ..feature_extractor.meta import _turns_to_reach
        from ..feature_extractor.players import (
            _calculate_k_limit,
            indicator_from_costs,
        )
        from ..bfs.turn_nav import TurnNavigation

        snap = ctx.memory._turn_extract_snapshot
        if snap is None:
            return

        item_entries = snap["items"]
        player_entries = snap["players"]
        menhir_distance = snap["menhir_distance"]
        observed_mist_distance = snap["observed_mist_distance"]

        item_positions = [(entry[1], entry[2]) for entry in item_entries[:4]]
        item_distances = [
            ctx.distances.get(coordinates.Coords(entry[1], entry[2]), 999)
            for entry in item_entries[:4]
        ]
        k = _calculate_k_limit(
            player_entries, ctx.memory, ctx.knowledge.no_of_champions_alive
        )
        enemy_positions = []
        enemy_facings = []
        enemy_indicators: list[float] = []
        turn_nav = TurnNavigation.get(ctx.memory)
        for entry in player_entries[:k]:
            pos = coordinates.Coords(entry[3], entry[4])
            enemy_positions.append(pos)
            tile = ctx.memory.map_data.get(pos)
            if tile and tile.character:
                enemy_facings.append(tile.character.facing)
            else:
                enemy_facings.append(characters.Facing.UP)
            val_opp, val_me, return_cost = entry[0], entry[1], entry[2]
            if turn_nav is not None:
                enemy_indicators.append(
                    indicator_from_costs(
                        ctx.knowledge.position,
                        turn_nav,
                        val_opp,
                        val_me,
                        return_cost,
                    )
                )
        turns_to_reach = _turns_to_reach(
            menhir_distance,
            ctx.memory.mist_radius,
            ctx.knowledge.no_of_champions_alive,
            ctx.memory.mist_tick_counter,
        )

        pos_dist = {
            "times": dict(ctx.distances.times),
            "hp_lost": dict(ctx.distances.hp_lost),
        }

        self.last_debug_state = {
            "outputs": outputs,
            "masked_scores": masked_scores,
            "best_idx": best_idx,
            "inputs": features,
            "position_distances": pos_dist,
            "item_positions": item_positions,
            "item_distances": item_distances,
            "enemy_positions": enemy_positions,
            "enemy_indicators": enemy_indicators,
            "menhir_distance": menhir_distance,
            "observed_mist_distance": observed_mist_distance,
            "turns_to_reach": turns_to_reach,
            "msg": msg,
            "bot_pos": ctx.knowledge.position,
            "bot_facing": facing,
            "enemy_facings": enemy_facings,
            "episode_time": episode_time,
        }


__all__ = ["Brain"]
