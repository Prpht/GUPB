from typing import List, Optional, Protocol
from gupb.controller.dart.movement_mechanics import MovemetMechanics
from gupb.model.arenas import ArenaDescription
from gupb.model.characters import Action, ChampionKnowledge
from gupb.model.coordinates import Coords


class Strategy(Protocol):
    def reset(self, arena_description: ArenaDescription) -> None:
        ...

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        ...


class RunAwayStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__()
        self._movement_mechanics: Optional[MovemetMechanics] = None
        self._destination: Optional[Coords] = None
        self._path: Optional[List[Coords]] = None
        self._previous_action: Action = Action.DO_NOTHING

    def reset(self, arena_description: ArenaDescription) -> None:
        self._movement_mechanics = MovemetMechanics(arena_description)
        self._destination = self._movement_mechanics.find_middle_cords()

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        if self._path is None:
            self._path = self._movement_mechanics.find_path(knowledge.position, self._destination)

        return self._follow_path(knowledge) if self._path else self._rotate_and_attack()

    def _follow_path(self, knowledge: ChampionKnowledge) -> Action:
        if knowledge.position == self._path[0]:
            self._path.pop(0)
        if not self._path:
            return Action.ATTACK
        next_position = Coords(*self._path[0])
        current_facing = self._movement_mechanics.get_facing(knowledge)
        desired_facing = self._movement_mechanics.get_desired_facing(knowledge.position, next_position)
        return self._movement_mechanics.determine_action(current_facing, desired_facing)

    def _rotate_and_attack(self) -> Action:
        desired_action = Action.TURN_RIGHT if self._previous_action == Action.ATTACK else Action.ATTACK
        self._previous_action = desired_action
        return desired_action
