import random
from typing import List, Optional
from gupb.controller import Controller
from gupb.controller.dart.movement_mechanics import euclidean_distance, get_champion_weapon
from gupb.controller.dart.strategy import AttackOpponentStrategy, CollectClosestWeaponStrategy, GoToMenhirStrategy, RotateAndAttackStrategy, RunAwayFromOpponentStrategy, Strategy
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
        self._arena_description: Optional[ArenaDescription] = None
        self._strategy_queue: List[Strategy] = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DartController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def _get_strategy(self) -> Strategy:
        return self._strategy_queue[-1]

    def _set_strategy(self, strategy: Strategy) -> None:
        if not self._strategy_queue or self._strategy_queue[-1].__class__ != strategy.__class__:
            self._strategy_queue.append(strategy)

    def _reset_strategy(self, strategy: Strategy) -> None:
        if self._strategy_queue[-1].__class__ != strategy.__class__:
            self._strategy_queue = [strategy]

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        try:
            # Handle mist observed
            if self._get_strategy().map_knowledge.mist_coords:
                self._reset_strategy(GoToMenhirStrategy(self._arena_description))

            # Handle opponent found
            elif self._get_strategy().map_knowledge.opponents:
                opponents_coords = list(self._get_strategy().map_knowledge.opponents.values())
                opponent_coords = self._get_strategy().map_knowledge.find_closest_coords(knowledge.position, opponents_coords)
                if euclidean_distance(knowledge.position, opponent_coords) < 3:
                    self._set_strategy(AttackOpponentStrategy(self._arena_description, opponent_coords))
                    return self._get_strategy().decide(knowledge)
                elif euclidean_distance(knowledge.position, opponent_coords) < 5:
                    self._set_strategy(RunAwayFromOpponentStrategy(self._arena_description, opponent_coords))
                    return self._get_strategy().decide(knowledge)

            action = self._get_strategy().decide(knowledge)
            if action:
                return action
            self._strategy_queue.pop()

            # Default
            if get_champion_weapon(knowledge) != "knife":
                self._set_strategy(RotateAndAttackStrategy(self._arena_description))
            else:
                self._set_strategy(CollectClosestWeaponStrategy(self._arena_description))

            return self._get_strategy().decide(knowledge)
        except Exception as e:
            return random.choice(POSSIBLE_ACTIONS)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: ArenaDescription) -> None:
        self._arena_description = arena_description
        self._strategy_queue = [CollectClosestWeaponStrategy(arena_description)]

    @property
    def name(self) -> str:
        return f'DartController{self.first_name}'

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.ORANGE
