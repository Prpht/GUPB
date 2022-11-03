import random
from typing import Optional
from gupb.controller import Controller
from gupb.controller.dart.movement_mechanics import MapKnowledge
from gupb.controller.dart.strategies import DefaultStrategy, Strategy
from gupb.model.arenas import ArenaDescription
from gupb.model.characters import Action, ChampionKnowledge, Tabard

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class DartController(Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self._map_knowledge: Optional[MapKnowledge] = None
        self._strategy: Strategy = DefaultStrategy()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DartController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        try:
            self._map_knowledge.update_map_knowledge(knowledge)
            return self._strategy.decide(knowledge, self._map_knowledge)
        except Exception as e:
            return random.choice(POSSIBLE_ACTIONS)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: ArenaDescription) -> None:
        self._map_knowledge = MapKnowledge(arena_description)

    @property
    def name(self) -> str:
        return f'DartController{self.first_name}'

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.ORANGE
