import os
from collections import deque

import random
import pylab
from tensorflow.keras.models import load_model
from PER import *
from model import build_model


class DQNAgent:
    def __init__(self, env, name):
        self.env = env
        self.env.seed(0)
        self.name = name

        self.env._max_episode_steps = 150
        self.state_size = self.env.observation_space.shape
        self.action_size = self.env.action_space.n
        self.EPISODES = 2000

        # Instantiate memory
        memory_size = 10000
        self.MEMORY = Memory(memory_size)
        self.memory = deque(maxlen=2000)

        self.gamma = 0.95    # discount rate

        # EXPLORATION HYPERPARAMETERS for epsilon and epsilon greedy strategy
        self.epsilon = 1.0  # exploration probability at start
        self.epsilon_min = 0.01  # minimum exploration probability
        self.epsilon_decay = 0.0001  # exponential decay rate for exploration prob

        self.batch_size = 32

        # defining model parameters
        self.ddqn = True # use doudle deep q network
        self.Soft_Update = False # use soft parameter update
        self.dueling = True # use dealing netowrk
        self.epsilon_greedy = True # use epsilon greedy strategy
        self.USE_PER = True # use priority experienced replay

        self.TAU = 0.1 # target network soft update hyperparameter

        self.Save_Path = 'Models'
        if not os.path.exists(self.Save_Path): os.makedirs(self.Save_Path)
        self.scores, self.episodes, self.average = [], [], []

        self.Model_name = os.path.join(self.Save_Path, self.name + "_PER_D3QN_CNN.h5")

        # create main model and target model
        self.model = build_model(input_shape=self.state_size, action_space = self.action_size, dueling = self.dueling)
        self.target_model = build_model(input_shape=self.state_size, action_space = self.action_size, dueling = self.dueling)

        # after some time interval update the target model to be same with model
    def update_target_model(self):
        if not self.Soft_Update and self.ddqn:
            self.target_model.set_weights(self.model.get_weights())
            return
        if self.Soft_Update and self.ddqn:
            q_model_theta = self.model.get_weights()
            target_model_theta = self.target_model.get_weights()
            counter = 0
            for q_weight, target_weight in zip(q_model_theta, target_model_theta):
                target_weight = target_weight * ( 1 -self.TAU) + q_weight * self.TAU
                target_model_theta[counter] = target_weight
                counter += 1
            self.target_model.set_weights(target_model_theta)

    def remember(self, state, action, reward, next_state, done):
        experience = state, action, reward, next_state, done
        if self.USE_PER:
            self.MEMORY.store(experience)
        else:
            self.memory.append((experience))

    def act(self, state, decay_step):
        if self.epsilon_greedy:
            # Here we'll use an improved version of our epsilon greedy strategy for Q-learning
            explore_probability = self.epsilon_min + (self.epsilon - self.epsilon_min) * np.exp(-self.epsilon_decay * decay_step)
        else:
            if self.epsilon > self.epsilon_min:
                self.epsilon *= ( 1 -self.epsilon_decay)
            explore_probability = self.epsilon

        if explore_probability > np.random.rand():
            # Make a random action (exploration)
            return random.randrange(self.action_size), explore_probability
        else:
            # Get action from Q-network (exploitation)
            return np.argmax(self.model.predict(state.reshape(-1, *self.state_size))), explore_probability

    def replay(self):
        if self.USE_PER:
            # Sample minibatch from the PER memory
            tree_idx, minibatch  = self.MEMORY.sample(self.batch_size)
        else:
            # Randomly sample minibatch from the deque memory
            minibatch = random.sample(self.memory, min(len(self.memory), self.batch_size))

        state = np.zeros((self.batch_size,) + self.state_size)
        next_state = np.zeros((self.batch_size,) + self.state_size)
        action, reward, done = [], [], []

        for i in range(len(minibatch)):
            state[i] = minibatch[i][0]
            action.append(minibatch[i][1])
            reward.append(minibatch[i][2])
            next_state[i] = minibatch[i][3]
            done.append(minibatch[i][4])

        # predict Q-values for starting state using the main network
        target = self.model.predict(state)
        target_old = np.array(target)
        # predict best action in ending state using the main network
        target_next = self.model.predict(next_state)
        # predict Q-values for ending state using the target network
        target_val = self.target_model.predict(next_state)

        for i in range(len(minibatch)):
            # correction on the Q value for the action used
            if done[i]:
                target[i][action[i]] = reward[i]
            else:
                # the key point of Double DQN
                # selection of action is from model
                # update is from target model
                if self.ddqn: # Double - DQN
                    # current Q Network selects the action
                    # a'_max = argmax_a' Q(s', a')
                    a = np.argmax(target_next[i])
                    # target Q Network evaluates the action
                    # Q_max = Q_target(s', a'_max)
                    target[i][action[i]] = reward[i] + self.gamma * (target_val[i][a])
                else: # Standard - DQN
                    # DQN chooses the max Q value among next actions
                    # selection and evaluation of action is on the target Q Network
                    # Q_max = max_a' Q_target(s', a')
                    target[i][action[i]] = reward[i] + self.gamma * (np.amax(target_next[i]))

        if self.USE_PER:
            indices = np.arange(self.batch_size, dtype=np.int32)
            absolute_errors = np.abs(target_old[indices, np.array(action) ] -target[indices, np.array(action)])
            self.MEMORY.batch_update(tree_idx, absolute_errors)

        self.model.fit(state, target, batch_size=self.batch_size, verbose=0)

    def load(self, name):
        self.model = load_model(name)

    def save(self, name):
        self.model.save(name)

    pylab.figure(figsize=(18, 9))
    def PlotModel(self, score, episode):
        self.scores.append(score)
        self.episodes.append(episode)
        self.average.append(sum(self.scores[-50:]) / len(self.scores[-50:]))
        pylab.plot(self.episodes, self.scores, 'b')
        pylab.plot(self.episodes, self.average, 'r')
        pylab.ylabel('Score', fontsize=18)
        pylab.xlabel('Steps', fontsize=18)
        dqn = 'DQN_'
        softupdate = ''
        dueling = ''
        greedy = ''
        PER = ''
        if self.ddqn: dqn = 'DDQN_'
        if self.Soft_Update: softupdate = '_soft'
        if self.dueling: dueling = '_Dueling'
        if self.epsilon_greedy: greedy = '_Greedy'
        if self.USE_PER: PER = '_PER'
        try:
            pylab.savefig(dqn+self.name+softupdate+dueling+greedy+PER+"_CNN.png")
        except OSError:
            pass

        return str(self.average[-1])[:5]

    def reset(self):
        state = self.env.reset()
        return state

    def step(self ,action):
        next_state, reward, done, info = self.env.step(action)
        return next_state, reward, done, info

    def run(self):
        decay_step = 0
        for e in range(self.EPISODES):
            state = self.reset()
            done = False
            i = 0
            while not done:
                decay_step += 1
                action, explore_probability = self.act(state, decay_step)
                next_state, reward, done, _ = self.step(action)
                if not done or i == self.env._max_episode_steps -1:
                    reward = reward
                else:
                    reward = -100
                self.remember(state, action, reward, next_state, done)
                state = next_state
                i += 1
                if done:
                    self.update_target_model()

                    average = self.PlotModel(i, e)
                    print(self.env.champion.position, self.env.controller.menhir_position)
                    print("episode: {}/{}, score: {}, e: {:.2}, average: {}".format(e, self.EPISODES, i, explore_probability, average))
                    if i == self.env._max_episode_steps:
                        print("Saving trained model to", self.Model_name)
                        # self.save(self.Model_name)
                        break
                self.replay()
            if (e + 1) % 500 == 0:
                print("Saving trained model to", f"{self.Model_name}_{e + 1}")
                self.save(f"{self.Model_name}_{e + 1}")
        self.save(self.Model_name)
        self.env.close()

    def test(self):
        self.load(self.Model_name)
        for e in range(self.EPISODES):
            state = self.reset()
            done = False
            i = 0
            while not done:
                action = np.argmax(self.model.predict(state))
                next_state, reward, done, _ = self.env.step(action)
                i += 1
                if done:
                    print("episode: {}/{}, score: {}".format(e, self.EPISODES, i))
                    break
