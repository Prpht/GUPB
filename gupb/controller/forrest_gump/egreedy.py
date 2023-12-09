import numpy as np


class EGreedy:
    def __init__(self, n_arms: int, epsilon: float, optimistic_start: float, offset: int) -> None:
        self.Q = np.ones(n_arms) * optimistic_start
        self.N = np.ones(n_arms)

        self.action = None
        self.e = epsilon
        self.offset = offset

    def __call__(self, reward: float) -> int:
        if self.action is not None:
            self.N[self.action] += 1
            self.Q[self.action] += (reward - self.Q[self.action]) / self.N[self.action]

        if np.random.rand() < self.e:
            self.action = np.random.randint(0, len(self.Q))
        else:
            self.action = np.argmax(self.Q)

        return self.action + self.offset
