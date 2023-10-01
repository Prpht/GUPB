import numpy as np
import random



class KArmedBandit():
    
    def __init__(self, arms=4):
        self._arms = arms
        self.epsilon = 0.3
        self.N = np.zeros(arms, dtype=np.float32) # self.N[0] = 1
        self.Q = np.zeros(arms, dtype=np.float32) # self.Q[0] = 0
        # self.Q = np.array([0, 0, 0, ,0], dtype=np.float32)
        self.current_action = 0

    def reward(self, score):
        # score = score/_fibonacci_of(13)
        gain = (1/self.N[self.current_action]) * (score - self.Q[self.current_action])
        self.Q[self.current_action] = self.Q[self.current_action] + gain
        self.write_to_file(score)

    def pull_arm(self):
        x = np.random.uniform() # 0..1
        if x < self.epsilon: # 10% na random
            self.current_action = random.choice(range(0, self._arms))
        else:
            self.current_action = np.argmax(self.Q)
        self.N[self.current_action] += 1
        return self.current_action

    def write_to_file(self, score):
        with open("k_armed_bandit_q.txt", "a") as f:
            f.write(f"{str(self.Q)}\n")

        with open("k_armed_bandit_n.txt", "a") as f:
            f.write(f"{str(self.N)}\n")

        with open("score.txt", "a") as f:
            f.write(f"{str(score)}\n")
