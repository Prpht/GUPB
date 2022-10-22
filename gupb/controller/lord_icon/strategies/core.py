
from abc import abstractmethod
from typing import NamedTuple
from gupb.controller.lord_icon.knowledge import Knowledge

from gupb.model.characters import Action


class Strategy(NamedTuple):
    name: str

    @abstractmethod
    def get_action(self, knowledge: Knowledge) -> Action:
        pass
