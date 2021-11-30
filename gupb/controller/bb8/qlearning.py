import random
from collections import defaultdict
from enum import Enum

class MistDistance(Enum):
    NO_MIST = 1,
    FAR_MIST = 2, 
    CLOSE_MIST = 3

class QAction(Enum):
    RUN_AWAY = 1,
    IGNORE = 2
  
q_values = defaultdict(int) # (state, action): reward
epsilon = 0.2
learning_rate = 0.3
gamma = 0.99

mist_threshold = 2000

def choose_action(state):
    return get_max_reward_action(state)

def get_max_reward_action(state):
    action_dict = { action: q_values[(state, action)] for action in QAction }
    return max(action_dict, key = action_dict.get)

def learn_actions(state):
    if random.uniform(0, 1) < epsilon:
        # explore: select a random action
        action = random.choice([QAction.RUN_AWAY, QAction.IGNORE])
        return (state, action)
    else:
        # exploit: select the action with max value (future reward)
        action = get_max_reward_action(state)
        return (state, action)

def update_q_values(old_state, action, reward, new_state):
    q_values[(old_state, action)] = q_values[(old_state, action)] + learning_rate * \
        (reward + gamma * q_values[(new_state, get_max_reward_action(new_state))] - q_values[(old_state, action)])

def calculate_state(mist_vec):
    g_distance_vec = lambda vec: ((vec[0]) ** 2 + (vec[1]) ** 2)

    if mist_vec is None:
        return MistDistance.NO_MIST
    if g_distance_vec(mist_vec) < mist_threshold:
        return MistDistance.CLOSE_MIST
    else:
        return MistDistance.FAR_MIST

def get_table():
    return q_values
