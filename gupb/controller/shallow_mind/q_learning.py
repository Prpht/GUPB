import math
from collections import defaultdict
from random import random, choice
from typing import Dict, Tuple, NamedTuple

import numpy as np

from gupb.controller.shallow_mind.arenna_wrapper import ArenaWrapper
from gupb.controller.shallow_mind.consts import REWARD_CONST, DISCOUNT_FACTOR, LEARNING_RATE, StrategyAction, EPSILON, \
    PUNISHMENT_CONST, MIST_BINS, DIST_PROPORTION_BINS, LEARN, DIST_BINS, LEARNING_CHANGE_COUNT, LEARNING_RATE_CHANGE, \
    LEARNING_RATE_MIN, DISCOUNT_FACTOR_CHANGE, DISCOUNT_FACTOR_MAX
from gupb.controller.shallow_mind.utils import points_dist

State = NamedTuple('State', [('menhir', int), ('proportion', int), ('mist', int)])


def default_value():
    return 0


class QLearning:
    def __init__(self, knowledge=None):
        if knowledge is None:
            knowledge = {}
        self.q: Dict[Tuple[State, StrategyAction], float] = defaultdict(default_value, knowledge)
        self.old_state: State = None
        self.old_action: StrategyAction = None
        self.reward_sum: float = 0.0
        self.episodes: int = 0

    def reset(self, arena: ArenaWrapper) -> float:
        self.old_state = None
        self.old_action = None
        reward_sum = self.reward_sum
        self.reward_sum = 0.0
        self.episodes += 1
        return reward_sum

    def best_action(self, state: State) -> StrategyAction:
        actions = {action: self.q[(state, action)] for action in StrategyAction}
        return max(actions, key=actions.get)

    def pick_action(self, state: State) -> StrategyAction:
        if LEARN and random() < EPSILON:
            return choice(list(StrategyAction))
        else:
            return self.best_action(state)

    def update_q(self, state: State, action: StrategyAction, reward: int) -> None:
        multiplier = math.floor(self.episodes / LEARNING_CHANGE_COUNT)
        learning_rate = max(LEARNING_RATE_MIN,
                            LEARNING_RATE - multiplier * LEARNING_RATE_CHANGE)
        discount_factor = min(DISCOUNT_FACTOR_MAX, DISCOUNT_FACTOR + multiplier * DISCOUNT_FACTOR_CHANGE)
        if self.old_state and self.old_action:
            self.q[(self.old_state, self.old_action)] += learning_rate * (
                    reward + discount_factor * self.q[(state, action)] - self.q[(self.old_state, self.old_action)])
        self.old_action = action
        self.old_state = state

    def attempt(self, arena: ArenaWrapper) -> StrategyAction:
        state = self.discretise(arena)
        action = self.pick_action(state)
        if LEARN:
            reward = self.calculate_reward(arena)
            self.reward_sum += reward
            self.update_q(state, action, reward)
        return action

    def discretise(self, arena: ArenaWrapper) -> State:
        mist_dist = arena.calc_mist_dist()
        menhir_dist = points_dist(arena.position, arena.menhir_destination)
        return State(np.digitize([arena.move_to_menhir.time], DIST_BINS)[0],
                     np.digitize([arena.move_to_menhir.time / menhir_dist], DIST_PROPORTION_BINS)[
                         0],
                     np.digitize([mist_dist], MIST_BINS)[0])

    def calculate_reward(self, arena: ArenaWrapper) -> int:
        dist = arena.calc_mist_dist()
        if dist > 0:
            if dist > 10 and self.old_action == StrategyAction.GO_TO_MENHIR:
                return -5
            return math.floor(REWARD_CONST / dist)
        if arena.position == arena.menhir_destination:
            return 1
        elif dist == 0 or self.old_action == StrategyAction.GO_TO_MENHIR:
            return PUNISHMENT_CONST * -1
        else:
            return PUNISHMENT_CONST * dist
