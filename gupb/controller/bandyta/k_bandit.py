import random
from typing import Optional

from gupb.controller.bandyta.tactics import Tactics


class K_Bandit:
    def __init__(self):
        self.Q = {tactic: 0 for tactic in Tactics}
        self.N = {tactic: 0 for tactic in Tactics}
        self.EPS = 0.2
        self.tactic: Optional[Tactics] = None

    def choose_tactic(self) -> Tactics:
        best_action = max(self.Q, key=self.Q.get)
        not_checked_actions = [action for action, value in self.Q.items() if value == 0]
        preferred_actions = [best_action, *not_checked_actions]
        not_preferred_actions = [action for action, value in self.Q.items() if action not in preferred_actions]

        if len(not_preferred_actions) == 0:
            not_preferred_actions = preferred_actions

        self.tactic = (
            random.choice(preferred_actions)
            if random.choices([True, False], weights=[1 - self.EPS, self.EPS], k=1) else
            random.choice(not_preferred_actions))

        return self.tactic

    def learn(self, score):
        self.N[self.tactic] += 1
        q, n = self.Q[self.tactic], self.N[self.tactic]
        self.Q[self.tactic] = q + (1 / n) * (score - q)
