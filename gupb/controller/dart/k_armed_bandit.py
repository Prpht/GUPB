import numpy as np
import random



class KArmedBandit():
    
    def __init__(self, arms):
        self.epsilon = 0.1
        self.N = np.zeros(arms) # self.N[0] = 1
        self.Q = np.zeros(arms) # self.Q[0] = 0
        self.current_action = 0

    def reward(self, score):
        score = (score/(_fibonacci_of(13)[:-1]))
        gain = (1/self.N[self.current_action]) * (score - self.Q[self.current_action])
        self.Q[self.current_action] = self.Q[self.current_action] + gain
        self.write_to_file()

    def pull_arm(self):
        x = np.random.uniform() # 0..1
        if x < self.epsilon: # 10% na random
            self.current_action = random.choice(range(0, arms))
        else:
            self.current_action = np.argmax(self.Q)
        self.N[self.current_action] += 1
        return self.current_action

    def write_to_file(self):
        with open("k_armed_bandit_q.txt", "a") as f:
            f.write(self.Q)

        with open("k_armed_bandit_n.txt", "a") as f:
            f.write(self.N)

    def _fibonacci_of(n):
        if n in {0, 1}:
            return n
        return _fibonacci_of(n - 1) + _fibonacci_of(n - 2)
