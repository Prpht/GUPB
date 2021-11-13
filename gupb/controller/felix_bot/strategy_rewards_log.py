from collections import defaultdict


class StrategyRewardsLog:
    def __init__(self):
        self.total_actions = 0
        self.total_rewards = 0
        self.all_rewards = []
        self.record = defaultdict(lambda: dict(actions=1, reward=55))

    def record_action(self, strategy, reward):
        self.total_actions += 1
        self.total_rewards += reward
        self.all_rewards.append(reward)
        self.record[strategy]['actions'] += 1
        self.record[strategy]['reward'] += reward

    def __getitem__(self, strategy):
        return self.record[strategy]