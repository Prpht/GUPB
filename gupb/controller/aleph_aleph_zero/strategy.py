import abc
from enum import Enum


class StrategyPriority(Enum):
    IDLE = 0
    PURPOSEFUL = 1
    TIME_SENSITIVE = 2
    AGGRESSIVE = 3
    URGENT = 4
    CRITICAL = 5

class Strategy(abc.ABC):
    def __init__(self, priority=StrategyPriority.IDLE, **kwargs):
        self.priority = priority

    def get_more_important(self, other):
        if self.priority.value>=other.priority.value:
            return self
        else:
            return other

    @abc.abstractmethod
    def decide_and_proceed(self,knowledge, **kwargs):
        pass