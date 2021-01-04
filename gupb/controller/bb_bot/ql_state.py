"""
State
menhir x-dist
menhir y-dist
front-wall dist
mist x-dist
mist y-dist
"""
from enum import Enum
from functools import reduce
import matplotlib.pyplot as plt

from gupb.model import coordinates, characters, arenas

import numpy as np
import os
import json
import matplotlib.ticker as ticker

M_DIST_CAP = 10

MENHIR_REW = 30

EPSILON = 0.9
# EPSILON = 1
GAMMA = 0.96
LR = 0.4

MODEL_NAME = "mist-runner"
GAMES_FREQ = 200
N = 3


class QAction(Enum):
    UP = coordinates.Coords(0, -1)
    RIGHT = coordinates.Coords(1, 0)
    DOWN = coordinates.Coords(0, 1)
    LEFT = coordinates.Coords(-1, 0)


QActions = list(QAction)


def get_state(position: coordinates.Coords, facing: characters.Facing, controller):
    # import code;
    # code.interact(local=dict(globals(), **locals()))
    x = M_DIST_CAP
    y = M_DIST_CAP
    for coords in controller.arena.terrain:
        if len(controller.arena.terrain[coords].effects) == 0 or not controller.arena.terrain[coords].effects[0].description().type == 'mist':
            continue

        nx = coords.x - position.x
        ny = coords.y - position.y

        if abs(nx) < abs(x):
            x = nx
        if abs(ny) < abs(y):
            y = ny

    return (
        max(min(x, M_DIST_CAP), -M_DIST_CAP) + M_DIST_CAP,
        max(min(y, M_DIST_CAP), -M_DIST_CAP) + M_DIST_CAP,
    )


class Model:

    def __init__(self):
        table_shape = (M_DIST_CAP * 2 + 1, M_DIST_CAP * 2 + 1, len(QActions))
        self.q_table = np.zeros(table_shape)
        self.hits = np.zeros(table_shape, dtype=np.int)
        self.rewards = []

    def make_heatmap(self, controller):
        games = len(self.rewards)

        if GAMES_FREQ is None or games % GAMES_FREQ != 0:
            return

        heatmap = np.zeros(self.q_table.shape)

        labels = range(-M_DIST_CAP, M_DIST_CAP+1)
        ticks = range(len(labels))

        plt.clf()
        fig, (ax1, ax2, ax3, ax4, cax) = plt.subplots(1, 5, figsize=(14, 4))
        axes = [ax1, ax2, ax3, ax4]

        for dir in range(len(QActions)):
            for x in ticks:
                for y in ticks:
                    xv = labels[x]
                    yv = labels[y]

                    dx = max(min(xv, M_DIST_CAP), -M_DIST_CAP) + M_DIST_CAP
                    dy = max(min(yv, M_DIST_CAP), -M_DIST_CAP) + M_DIST_CAP
                    total =  np.sum(self.q_table[dx, dy, :])

                    v = self.q_table[dx, dy, dir] / total if total > 0.0 else -0.1
                    heatmap[y, x, dir] = v

            ax = axes[dir]
            ax.set_title(str(QActions[dir]))
            im = ax.imshow(heatmap[:,:,dir], cmap='viridis', vmin=-0.1, vmax=1.0)

            ax.xaxis.set_major_locator(ticker.FixedLocator(ticks))
            # ax.set_xticks(ticks, labels)
            ax.set_xticklabels(labels)
            ax.yaxis.set_major_locator(ticker.FixedLocator(ticks))
            # ax.set_yticks(ticks, labels)
            ax.set_yticklabels(labels)

        fig.tight_layout(pad=2.0)
        fig.colorbar(im, cax=cax)
        cax.set_box_aspect(4)

        plt.savefig("./bb_bot_resources/{}/heatmap_{}.png".format(MODEL_NAME, games))
        plt.close(fig)

    def plot_rewards(self):
        games = len(self.rewards)

        if GAMES_FREQ is None or games % GAMES_FREQ != 0:
            return

        window_size = 20

        i = 0
        moving_averages = []
        while i < len(self.rewards) - window_size + 1:
            window = self.rewards[i: i + window_size]
            window_average = np.mean(window)
            moving_averages.append(window_average)
            i += 1

        plt.clf()
        plt.plot(moving_averages)
        plt.savefig("./bb_bot_resources/{}/rewards_{}.png".format(MODEL_NAME, games))

    def audit_hits(self):
        games = len(self.rewards)

        if GAMES_FREQ is None or games % GAMES_FREQ != 0:
            return

        visited = len(np.where(self.hits > 0)[0])
        total = reduce(lambda a, b: a * b, self.hits.shape)
        print("Hitted: {:.3}".format(visited / total))

    def save(self):
        model_path = os.path.join("./bb_bot_resources", MODEL_NAME, "model.npy")
        hits_path = os.path.join("./bb_bot_resources", MODEL_NAME, "hits.npy")
        rewards_path = os.path.join("./bb_bot_resources", MODEL_NAME, "rewards.npy")

        with open(rewards_path, 'w') as file:
            file.write(json.dumps(self.rewards))
        np.save(model_path, self.q_table)
        np.save(hits_path, self.hits)

    def load(self):
        try:
            model_path = os.path.join("./bb_bot_resources", MODEL_NAME, "model.npy")
            hits_path = os.path.join("./bb_bot_resources", MODEL_NAME, "hits.npy")
            rewards_path = os.path.join("./bb_bot_resources", MODEL_NAME, "rewards.npy")

            with open(rewards_path, 'r') as file:
                self.rewards = json.load(file)

            self.q_table = np.load(model_path)
            self.hits = np.load(hits_path)
        except FileNotFoundError:
            pass

        return self


class LearningController:

    def __init__(self, model: Model, controller, learning=False):
        self.state = None
        self.model = model
        self.action = 0
        self.controller = controller
        self.menhir_reward = False
        self.eps = EPSILON if learning else 1.0

        self.rewards = 0
        self.uninitialized = True

    def episode(self, reward: int):
        state2 = self.determine_state()
        action2 = self.choose_action(state2)
        self.learn(self.state, self.action, reward, state2, action2)

        self.state = state2
        self.action = action2

        self.rewards += reward

        return self.state, self.action

    def apply_menhir_reward(self):
        menhir_pos: coordinates.Coords = self.controller.menhirPos
        distx = abs(menhir_pos.x - self.controller.currentPos.x)
        disty = abs(menhir_pos.y - self.controller.currentPos.y)
        if max(distx, disty) <= 1:
            return MENHIR_REW
        return 0

    def initial_ep(self):
        self.state = self.determine_state()
        self.action = self.choose_action(self.state)
        return self.state, self.action

    def determine_state(self):
        position = self.controller.knowledge.position
        return get_state(position, self.controller.facing, self.controller)

    def new_state(self, action: QAction):
        new_pos = self.controller.currentPos + action.value

        if not self.controller.arena.terrain[new_pos].passable:
            return self.state
        else:
            for facing in list(characters.Facing.UP):
                if facing.value == action.value:
                    return get_state(new_pos, facing, self.controller)

    def choose_action(self, state: tuple) -> int:
        if np.random.uniform(0, 1) < self.eps:
            action = np.random.randint(len(QActions))
        else:
            mx, my = state
            action = np.argmax(self.model.q_table[mx, my, :])
        return action

    def learn(self, state: tuple, action: int, reward: int, state2: tuple, action2: int):
        predict = self.Q(state, action)
        target = reward + GAMMA * self.Q(state2, action2)
        self.update_Q(state, action, LR * (target - predict))

    def final_learn(self, reward):
        predict = self.Q(self.state, self.action)
        self.update_Q(self.state, self.action, LR * (reward - predict))

    def Q(self, state: tuple, action: int):
        idx = state + (action,)
        return self.model.q_table[idx]

    def update_Q(self, state: tuple, action: int, value: float):
        idx = state + (action,)
        self.model.hits[idx] += 1
        self.model.q_table[idx] += value

    def explain_state(self, state):
        x = state[0] - M_DIST_CAP
        y = state[1] - M_DIST_CAP
        print("Mist is far by X: {};\tY: {};".format(x, y))

    def explain_action(self, action):
        print("Going {}".format(str(QActions[action])))

    def translate_action(self, action: int):
        turns = 0
        orient = self.controller.facing

        orient_i = [x.value for x in QActions].index(orient.value)

        while QActions[action].value != QActions[orient_i].value:
            turns += 1
            orient_i += 1
            orient_i %= len(QActions)

        turning = [characters.Action.TURN_LEFT] if turns == 3 else [characters.Action.TURN_RIGHT] * turns
        return [characters.Action.STEP_FORWARD] + turning
