import random
from typing import Tuple

import numpy as np

Batch = Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]


class ReplayMemory:

    def __init__(self, memory_size: int, frame_height: int, frame_width: int):
        self.__actions = np.empty(memory_size, dtype=np.int32)
        self.__rewards = np.empty(memory_size, dtype=np.float32)
        self.__current_states = np.empty(
            (memory_size, frame_height, frame_width), dtype=np.uint8
        )
        self.__next_states = np.empty(
            (memory_size, frame_height, frame_width), dtype=np.uint8
        )
        self.__terminal_flags = np.empty(memory_size, dtype=np.bool)
        self.__current_idx = 0
        self.__memory_size = memory_size

    def add_experience(
        self,
        state: np.ndarray,
        action: int,
        next_state: np.ndarray,
        reward: float,
        terminal: bool
    ) -> None:
        self.__current_states[self.__current_idx] = state
        self.__next_states[self.__current_idx] = next_state
        self.__actions[self.__current_idx] = action
        self.__rewards[self.__current_idx] = reward
        self.__terminal_flags[self.__current_idx] = terminal
        self.__current_idx = min(self.__current_idx + 1, self.__memory_size)

    def get_batch(self, batch_size: int) -> Batch:
        indices = np.array(random.choices(list(range(self.__memory_size)), k=batch_size))
        return (
            self.__current_states[indices],
            self.__actions[indices],
            self.__next_states[indices],
            self.__rewards[indices],
            self.__terminal_flags[indices]
        )
