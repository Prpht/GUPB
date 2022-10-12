from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional
from gupb.controller.dart.movement_mechanics import MapKnowledge, follow_path, is_opponent_in_front
from gupb.model.arenas import ArenaDescription
from gupb.model.characters import Action, ChampionKnowledge
from gupb.model.coordinates import Coords


class Steps(Enum):
    init = auto()
    find_axe = auto()
    go_to_center = auto()


class Strategy(ABC):
    def __init__(self) -> None:
        super().__init__()
        self._map_knowledge: Optional[MapKnowledge] = None
        self._path: Optional[List[Coords]] = None
        self._previous_position: Optional[Coords] = None

    @abstractmethod
    def decide(self, knowledge: ChampionKnowledge) -> Action:
        ...

    @abstractmethod
    def praise(self, score: int) -> None:
        ...

    def reset(self, arena_description: ArenaDescription) -> None:
        self._map_knowledge = MapKnowledge(arena_description)
        self._path = None
        self._previous_position = None

    def _follow_path(self, knowledge: ChampionKnowledge) -> Action:
        if knowledge.position == self._path[0]:
            self._path.pop(0)

        if not self._path:
            return Action.ATTACK
        if self._is_blocked_by_opponent(knowledge):
            return Action.ATTACK
        next_action = follow_path(self._path, knowledge)
        self._previous_position = knowledge.position
        return next_action

    def _is_blocked_by_opponent(self, knowledge: ChampionKnowledge) -> bool:
        return (knowledge.position == self._previous_position) and (is_opponent_in_front(self._path[0], knowledge.visible_tiles))


class AxeAndCenterStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__()
        self._state = Steps.init
        self._previous_action: Action = Action.DO_NOTHING

    def reset(self, arena_description: ArenaDescription) -> None:
        self._state = Steps.init
        self._previous_action = Action.DO_NOTHING
        return super().reset(arena_description)

    def praise(self, score: int) -> None:
        ...

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self._map_knowledge.update_weapons_positions()
        if not self._path:
            if self._state == Steps.init:
                self._path = self._map_knowledge.get_closest_weapon_path(knowledge.position, 'axe')
                self._state = Steps.find_axe
            elif self._state == Steps.find_axe:
                destination = self._map_knowledge.find_middle_cords()
                self._path = self._map_knowledge.find_path(knowledge.position, destination)
                self._state = Steps.go_to_center

        return self._follow_path(knowledge) if self._path else self._rotate_and_attack()

    def _rotate_and_attack(self) -> Action:
        desired_action = Action.TURN_RIGHT if self._previous_action == Action.ATTACK else Action.ATTACK
        self._previous_action = desired_action
        return desired_action
