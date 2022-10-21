import random
from typing import List, Optional, Type
from gupb.controller import Controller
from gupb.controller.dart.movement_mechanics import euclidean_distance, get_champion_weapon, is_opponent_in_front
from gupb.controller.dart.strategy import AttackOpponentStrategy, CollectClosestWeaponStrategy, GoToMenhirStrategy, RotateAndAttackStrategy, RunAwayFromOpponentStrategy, Strategy
from gupb.model.arenas import ArenaDescription
from gupb.model.characters import Action, ChampionKnowledge, Tabard
from gupb.model.coordinates import Coords

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
        self._strategy: Optional[Strategy] = None
        self._previous_opponent_coords: Optional[Coords] = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DartController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        try:
            # Handle mist observed
            for i in range(3):
                if not self._is_same_strategy(GoToMenhirStrategy) and self._strategy.map_knowledge.closest_mist_coords:
                    self._strategy = GoToMenhirStrategy(arena_description=self._arena_description)

                # Handle opponent found
                elif self._handle_opponent_strategy(knowledge):
                    self._strategy = self._handle_opponent_strategy(knowledge)                    
                
                # Choose different strategy
                else:
                    break

                action = self._strategy.decide(knowledge)
                if action:
                    return action

            action = self._strategy.decide(knowledge)
            if action and not self._is_same_strategy(CollectClosestWeaponStrategy) and not self._is_same_strategy(RotateAndAttackStrategy):
                return action

            # Handle collect weapon
            if not self._is_same_strategy(CollectClosestWeaponStrategy) and get_champion_weapon(knowledge) == "knife":
                self._strategy = CollectClosestWeaponStrategy(self._arena_description)

            # Default
            elif not self._is_same_strategy(RotateAndAttackStrategy):
                self._strategy = RotateAndAttackStrategy(self._arena_description)

            return self._strategy.decide(knowledge)
        except Exception as e:
            return random.choice(POSSIBLE_ACTIONS)
    
    def _handle_opponent_strategy(self, knowledge: ChampionKnowledge) -> Optional[Strategy]:
        if self._strategy.map_knowledge.opponents:
            if self._previous_opponent_coords in knowledge.visible_tiles and not is_opponent_in_front(self._previous_opponent_coords, knowledge.visible_tiles):
                self._previous_opponent_coords = None
            opponents_coords = list(self._strategy.map_knowledge.opponents.values())
            if self._previous_opponent_coords:
                opponents_coords.append(self._previous_opponent_coords)
            opponent_coords = self._strategy.map_knowledge.find_closest_coords(knowledge.position, opponents_coords)
            if euclidean_distance(knowledge.position, opponent_coords) < 3:
                self._previous_opponent_coords = opponent_coords
                return AttackOpponentStrategy(self._arena_description, opponent_coords)
            elif not self._is_same_strategy(RunAwayFromOpponentStrategy) and euclidean_distance(knowledge.position, opponent_coords) < 5:
                return RunAwayFromOpponentStrategy(self._arena_description, opponent_coords)
        return None

    def _is_same_strategy(self, strategy_class: Type[Strategy]) -> bool:
        self._strategy.__class__ == strategy_class

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: ArenaDescription) -> None:
        self._arena_description = arena_description
        self._strategy = CollectClosestWeaponStrategy(arena_description)
        self._previous_opponent_coords = None

    @property
    def name(self) -> str:
        return f'DartController{self.first_name}'

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.ORANGE
