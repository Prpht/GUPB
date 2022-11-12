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
    def __init__(self, priority=StrategyPriority.IDLE, signature=None, **kwargs):
        self.priority = priority
        self.signature = signature

    def get_more_important(self, other, exception_signature=None):
        if exception_signature is not None and exception_signature == self.signature:
            return self  # I've been given permission to keep priority for this specific place in the logic
            # (makes sense if you think about it long enough, I hope)

        if self.priority.value>other.priority.value:
            return self
        else:
            return other

    @abc.abstractmethod
    def decide_and_proceed(self,knowledge, **kwargs):
        pass