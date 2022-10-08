import abc


class Strategy(abc.ABC):
    @abc.abstractmethod
    def decide_and_proceed(self,knowledge, **kwargs):
        pass