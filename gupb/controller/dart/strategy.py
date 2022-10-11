from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Protocol
from gupb.controller.dart.movement_mechanics import PathFinder, find_shortest_path, follow_path, is_opponent_in_front
from gupb.model.arenas import ArenaDescription
from gupb.model.characters import Action, ChampionKnowledge
from gupb.model.coordinates import Coords
from gupb.model.tiles import TileDescription


class Steps(Enum):
    init = auto()
    find_axe = auto()
    go_to_center = auto()


class Strategy(Protocol):
    def reset(self, arena_description: ArenaDescription) -> None:
        ...

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        ...

    def praise(self, score: int) -> None:
        ...


class AxeAndCenterStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__()
        self._state = Steps.init
        self._path_finder: Optional[PathFinder] = None
        self._path: Optional[List[Coords]] = None
        self._previous_position: Optional[Coords] = None
        self._previous_action: Action = Action.DO_NOTHING

    def reset(self, arena_description: ArenaDescription) -> None:
        self._state = Steps.init
        self._path_finder = PathFinder(arena_description)
        self._path = None
        self._previous_position = None
        self._previous_action = Action.DO_NOTHING

    def praise(self, score: int) -> None:
        ...

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        if not self._path:
            if self._state == Steps.init:
                first_axe_path = self._path_finder.find_path(knowledge.position, Coords(13, 17))
                second_axe_path = self._path_finder.find_path(knowledge.position, Coords(38, 16))
                self._path = find_shortest_path(first_axe_path, second_axe_path)
                self._state = Steps.find_axe
            elif self._state == Steps.find_axe:
                destination = self._path_finder.find_middle_cords()
                self._path = self._path_finder.find_path(knowledge.position, destination)
                self._state = Steps.go_to_center

        return self._follow_path_strategy(knowledge) if self._path else self._rotate_and_attack_strategy()

    def get_champion_weapon(knowledge: ChampionKnowledge) -> str:
        return knowledge.visible_tiles[knowledge.position].character.weapon.name

    def _follow_path_strategy(self, knowledge: ChampionKnowledge) -> Action:
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

    def _rotate_and_attack_strategy(self) -> Action:
        desired_action = Action.TURN_RIGHT if self._previous_action == Action.ATTACK else Action.ATTACK
        self._previous_action = desired_action
        return desired_action
