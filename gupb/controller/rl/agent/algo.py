import stable_baselines3.dqn as dqn
import stable_baselines3.dqn.policies as policies

from gupb.controller.rl.environment.gupb import GUPBEnv


class Algo:
    def __init__(self, env: GUPBEnv) -> None:
        self._algo = dqn.DQN(
            env=env,
            policy=policies.MlpPolicy,
            learning_rate=0.01  # TODO provide as parameter
            # TODO Other params
        )

    def run(self):
        self._algo.learn(total_timesteps=1000)  # TODO provide as parameter
