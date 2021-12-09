from abc import ABC
from gupb import controller
from gupb.model import characters


class BaseMarwinController(controller.Controller, ABC):
    def __init__(self, first_name: str):
        self.first_name = first_name
        self._initial_health = characters.CHAMPION_STARTING_HP
        self._current_facing = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BaseMarwinController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    @property
    def name(self) -> str:
        return self.first_name

    def praise(self, score: int) -> None:
        pass

    def die(self) -> None:
        pass

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.LIME

    def _get_champion(self, knowledge: characters.ChampionKnowledge) -> characters.ChampionDescription:
        position = knowledge.position
        return knowledge.visible_tiles[position].character
