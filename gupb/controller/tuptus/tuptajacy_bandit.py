'''
Multi-armed bandit with e-greedy strategy
With saving all rewards for each arm
'''

import numpy as np
from random import randint
import random


class Bandit:
    def __init__(self, arms, epsilon):
        self.arms = arms
        self.epsilon = epsilon
        self.Q = np.ones(arms)
        self.rewards = [[] for _ in range(0, self.arms)]
        self.chosen_action = None
        self.rewards_list = []

    def choose_action(self):
        rand = np.random.uniform(0, 1)
        # select action with 1 - epsilon probability
        if rand > self.epsilon:
            # exploit
            argmax = np.argmax(self.Q) # select arm with best estimated reward
            self.chosen_action = argmax
            return argmax
        else:
            # explore
            self.chosen_action = randint(0, self.arms - 1)
            return self.chosen_action

    def get_reward(self, score):
        self.rewards_list.append((self.chosen_action, score)) 
        self.rewards[self.chosen_action].append(score)
        self.Q[self.chosen_action] = self.Q[self.chosen_action] + (1/len(self.rewards[self.chosen_action])) * (score - self.Q[self.chosen_action])
        if self.epsilon > 0.05:
            self.epsilon = self.epsilon - 0.005

    
