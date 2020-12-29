import random
from collections import defaultdict
from typing import NamedTuple, Dict
from enum import Enum
from gupb.model import characters

# Potencjalne stany:
# brak mgły
# Daleko -> 10+ i kierunek
# Blisko -> <10 i kierunek

# Akcje:
# uciekaj
# zostań

'''from that direction mist comes'''
class MistDirection(Enum):
    NORTH = 1,
    SOUTH = 2,
    EAST = 3,
    WEST = 4,
    ANY = 5

class MistDistance(Enum):
    NO_MIST = 1,
    FAR_MIST = 2, 
    CLOSE_MIST = 3

class QAction(Enum):
    RUN_AWAY = 1,
    IGNORE = 2

class QState:
    def __init__(self, mist_distance, mist_direct):
        self.mist_distance: MistDistance = mist_distance
        self.mist_direct: MistDirection = mist_direct

    def __eq__(self, other: object) -> bool:
        return self.mist_distance == other.mist_distance and self.mist_direct == other.mist_direct

    def __hash__(self) -> int:
        return 43

    def __str__(self):
        return str(self.mist_distance) + ", " + str(self.mist_direct)

    def __repr__(self):
        return str(self.mist_distance) + ", " + str(self.mist_direct)



  
# mapa: (stan, akcja) -> nagroda
q_values: Dict[(QState, QAction)] = defaultdict(int)
epsilon = 0.1
learning_rate = 0.3
gamma = 0.99

mist_threshold = 2000

# nauczony
def choose_action(state):
    return get_max_reward_action(state)

def get_max_reward_action(state):
    action_dict = { action: q_values[(state, action)] for action in QAction }
    return max(action_dict, key = action_dict.get)

def learn_actions(state):
    if random.uniform(0, 1) < epsilon:
        """
        Explore: select a random action
        """
        action = random.choice([QAction.RUN_AWAY, QAction.IGNORE])
        return (state, action)
    else:
        """
        Exploit: select the action with max value (future reward)
        """
        action = get_max_reward_action(state)
        return (state, action)


def update_q_values(old_state, action, reward, new_state):
    q_values[(old_state, action)] = q_values[(old_state, action)] + learning_rate * (reward + gamma * q_values[(new_state, get_max_reward_action(new_state))] - q_values[(old_state, action)])

def determine_state(mist_vec, bot_facing):

    mist_dist = calculate_mist_location(mist_vec)
    mist_direct = calculate_mist_direction(mist_vec, bot_facing)

    return QState(mist_dist, mist_direct)


def calculate_mist_location(mist_vec):
    g_distance_vec = lambda vec: ((vec[0]) ** 2 + (vec[1]) ** 2)
    if mist_vec is None:
        return MistDistance.NO_MIST
    if g_distance_vec(mist_vec) < mist_threshold:
        return MistDistance.CLOSE_MIST
    else:
        return MistDistance.FAR_MIST


def calculate_mist_direction(mist_vec, bot_facing):
    if mist_vec is None:
        return MistDirection.ANY
    if bot_facing == characters.Facing.UP or bot_facing == characters.Facing.DOWN:
        if is_mist_in_opposite(mist_vec, bot_facing):
            if bot_facing == characters.Facing.UP:
                return MistDirection.NORTH
            else:
                return MistDirection.SOUTH
        elif mist_vec[0] <= 0:
            return MistDirection.WEST
        else:
            return MistDirection.EAST
    else:
        if is_mist_in_opposite(mist_vec, bot_facing):
            if bot_facing == characters.Facing.RIGHT:
                return MistDirection.EAST
            else:
                return MistDirection.WEST
        elif mist_vec[1] <= 0:
            return MistDirection.NORTH
        else:
            return MistDirection.SOUTH


def is_mist_in_opposite(mist_vec, bot_facing):
    coords_diff_thresh = 5
    if bot_facing == characters.Facing.UP or bot_facing == characters.Facing.DOWN:
        x_coord_diff = abs(mist_vec[0])
        return  x_coord_diff <= coords_diff_thresh
    elif bot_facing == characters.Facing.LEFT or bot_facing == characters.Facing.RIGHT:
        x_coord_diff = abs(mist_vec[1])
        return  x_coord_diff <= coords_diff_thresh


def get_table():
    return q_values
