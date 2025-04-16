import abc


class BaseStrategy(abc.ABC):
    pass

    @abc.abstractmethod
    def apply(self):
        ...