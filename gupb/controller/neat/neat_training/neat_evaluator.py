from abc import abstractmethod

from typing_extensions import override

from gupb import runner
from gupb.controller.neat.kim_dzong_neat_jr import KimDzongNeatJuniorController


class NeatEvaluator:
    def __init__(self, controller: KimDzongNeatJuniorController, runner: runner.Runner):
        self.controller = controller
        self.runner = runner

    @abstractmethod
    def calculate_score(self):
        raise NotImplementedError("This method must be implemented in a subclass")


class NeatEvaluatorV1(NeatEvaluator):
    def __init__(self, controller: KimDzongNeatJuniorController, runner: runner.Runner):
        super().__init__(controller, runner)

    @override
    def calculate_score(self):
        return self.runner.scores["Kim Dzong Neat v_1"]
