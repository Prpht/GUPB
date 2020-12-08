from gupb.controller.bb_bot.helpers import facing_to_i, passable
from gupb.model import characters
from gupb.controller.bb_bot.model import Model

import numpy as np
import sys
import os
import random

EPSILON = 0.8
GAMMA = 0.96
LR = 0.81

ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.DO_NOTHING
]


class LearningController:

    def __init__(self, model: Model, char_controller):
        self.model = model
        self.state = None
        self.action = 0
        self.char_controller = char_controller

        self.facing_int = 0
        self.x = 0
        self.y = 0

        self.rewards = 0
        self.uninitialized = True

    def episode(self, reward, knowledge):
        try:
            state2 = self.determine_state(knowledge)
            action2 = self.choose_action(state2)
            self.learn(self.state, self.action, reward, state2, action2)
        except Exception as e:
            print(e)
            # import code;
            # code.interact(local=dict(globals(), **locals()))
            # print(e)

        self.state = state2
        self.action = action2

        self.rewards += reward

        return self.state, self.action

    def initial_ep(self, knowledge: characters.ChampionKnowledge):
        self.state = self.determine_state(knowledge)
        self.action = self.choose_action(self.state)
        return self.state, self.action

    def determine_state(self, knowledge: characters.ChampionKnowledge):
        self.x, self.y = knowledge.position.x, knowledge.position.y
        self.facing_int = facing_to_i[self.char_controller.facing]
        return (self.x, self.y, self.facing_int)

    def new_state(self, action):
        if action == characters.Action.STEP_FORWARD:
            new_pos = self.char_controller.currentPos + self.char_controller.facing
            if not passable(self.char_controller.arena, new_pos):
                new_pos = self.char_controller.currentPos

            return (new_pos.x, new_pos.y, facing_to_i[self.char_controller.facing])

        elif action == characters.Action.TURN_LEFT:
            new_facing_int = (self.facing_int + 3) % 4
            return (self.x, self.y, new_facing_int)
        elif action == characters.Action.TURN_RIGHT:
            new_facing_int = (self.facing_int + 1) % 4
            return (self.x, self.y, new_facing_int)
        else:
            return self.state

    def choose_action(self, state):
        action = 0
        if np.random.uniform(0, 1) < EPSILON:
            action = np.random.randint(len(ACTIONS))
        else:
            x, y, facing = state
            action = np.argmax(self.model.q_table[x, y, facing, :])
        return action

    def learn(self, state, action, reward, state2, action2):
        predict = self.Q(state, action)
        target = reward + GAMMA * self.Q(state2, action2)
        self.update_Q(state, action, LR * (target - predict))

    def Q(self, state, action):
        x, y, facing = state
        return self.model.q_table[x, y, facing, action]

    def update_Q(self, state, action, value):
        x, y, facing = state
        self.model.q_table[x, y, facing, action] += value
