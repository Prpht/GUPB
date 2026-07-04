import os
import pickle
import random
from typing import Dict, List, Optional, Tuple

State = Tuple[int, ...]
Key = Tuple[State, str]


class DoubleQTable:
    def __init__(
        self,
        modes: List[str],
        alpha: float = 0.1,
        gamma: float = 0.99,
        path: Optional[str] = None,
    ) -> None:
        self.modes = modes
        self.alpha = alpha
        self.gamma = gamma
        self.path = path
        self.q1: Dict[Key, float] = {}
        self.q2: Dict[Key, float] = {}
        self.games: int = 0
        self.epsilon: float = 0.30

    def load(self) -> bool:
        if self.path is None or not os.path.exists(self.path):
            return False
        try:
            with open(self.path, "rb") as f:
                data = pickle.load(f)
            self.q1 = dict(data["q1"])
            self.q2 = dict(data["q2"])
            self.games = int(data.get("games", 0))
            self.epsilon = float(data.get("epsilon", self.epsilon))
            return True
        except Exception:
            self.q1 = {}
            self.q2 = {}
            return False

    def save(self) -> None:
        if self.path is None:
            return
        data = {
            "q1": self.q1,
            "q2": self.q2,
            "games": self.games,
            "epsilon": self.epsilon,
        }
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "wb") as f:
            pickle.dump(data, f)
        os.replace(tmp_path, self.path)

    def value(self, state: State, mode: str) -> float:
        key = (state, mode)
        return self.q1.get(key, 0.0) + self.q2.get(key, 0.0)

    def known_state(self, state: State) -> bool:
        return any(
            (state, m) in self.q1 or (state, m) in self.q2 for m in self.modes
        )

    def best_mode(self, state: State) -> Optional[str]:
        if not self.known_state(state):
            return None
        return max(self.modes, key=lambda m: self.value(state, m))

    def select(self, state: State) -> str:
        if random.random() < self.epsilon:
            return random.choice(self.modes)
        return max(self.modes, key=lambda m: self.value(state, m))

    def update(
        self,
        state: State,
        mode: str,
        reward: float,
        tau: int,
        next_state: Optional[State],
    ) -> None:
        if random.random() < 0.5:
            primary, secondary = self.q1, self.q2
        else:
            primary, secondary = self.q2, self.q1
        target = reward
        if next_state is not None:
            best = max(
                self.modes, key=lambda m: primary.get((next_state, m), 0.0)
            )
            target += (self.gamma ** tau) * secondary.get((next_state, best), 0.0)
        key = (state, mode)
        old = primary.get(key, 0.0)
        primary[key] = old + self.alpha * (target - old)

    def states_seen(self) -> int:
        return len({key[0] for key in self.q1} | {key[0] for key in self.q2})
