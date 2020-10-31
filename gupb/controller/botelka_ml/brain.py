import random
from collections import deque, defaultdict
from typing import List, Tuple

import keras
import numpy as np

from gupb.controller.botelka_ml.models import Wisdom
from gupb.controller.botelka_ml.rewards import calculate_reward
from gupb.model.characters import Action, Facing
import keras

from gupb.model.characters import Action

EPS = 0.05

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]

ALPHA = 0.05
DECAY = 0.005
GAMMA = 0.9

q = defaultdict(int)


def pick_action(state: Tuple[int, int, int]) -> Action:
    rewards = {
        Action.TURN_LEFT: q[state, Action.TURN_LEFT],
        Action.TURN_RIGHT: q[state, Action.TURN_RIGHT],
        Action.STEP_FORWARD: q[state, Action.STEP_FORWARD],
        Action.ATTACK: q[state, Action.ATTACK],
    }
    best_action_value = rewards[sorted(rewards, key=rewards.get)[-1]]

    # Choose randomly if there are more actions with the same value
    actions = [
        action
        for action, value in rewards.items()
        if value == best_action_value
    ]
    return random.choice(actions)


def epsilon_greedy_action(q, state) -> Action:
    actions = [Action.TURN_LEFT, Action.TURN_RIGHT, Action.STEP_FORWARD, Action.ATTACK]

    if random.random() < EPS:
        return random.choice(actions)

    values = {q[state, action]: action for action in actions}

    return values[max(values)]


def get_state(wisdom: Wisdom) -> Tuple[int, int, int, int]:
    return (
        int(wisdom.can_attack_player), int(wisdom.mist_visible), int(wisdom.better_weapon_visible),
        int(wisdom.distance_to_menhir)
    )
