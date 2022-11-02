from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional
from gupb.controller.dart.movement_mechanics import MapKnowledge, determine_rotation_action, follow_path, get_facing, is_opponent_at_coords
from gupb.model.arenas import ArenaDescription
from gupb.model.characters import Action, ChampionKnowledge
from gupb.model.coordinates import Coords

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]


class Steps(Enum):
    init = auto()
    weapon_found = auto()
    mist_found = auto()


class Mode(Enum):
    run_away = auto()
    attack = auto()


class Strategy(ABC):
    def __init__(self, arena_description: ArenaDescription) -> None:
        super().__init__()
        self.map_knowledge = MapKnowledge(arena_description)
        self._path: Optional[List[Coords]] = None
        self._previous_position: Optional[Coords] = None

    @abstractmethod
    def decide(self, knowledge: ChampionKnowledge) -> Optional[Action]:
        self.map_knowledge.update_weapons_positions(knowledge)
        self.map_knowledge.update_map_knowledge(knowledge, knowledge.visible_tiles)

    def _action_follow_path(self, knowledge: ChampionKnowledge) -> Optional[Action]:
        if not self._path:
            return None

        if knowledge.position == self._path[0]:
            self._path.pop(0)

        if not self._path:
            return None

        if self._is_blocked_by_opponent(knowledge):
            return Action.ATTACK

        next_action = follow_path(self._path, knowledge)
        self._previous_position = knowledge.position
        return next_action

    def _is_blocked_by_opponent(self, knowledge: ChampionKnowledge) -> bool:
        return (knowledge.position == self._previous_position) and (is_opponent_at_coords(self._path[0], knowledge.visible_tiles))


class RotateAndAttackStrategy(Strategy):
    def __init__(self, arena_description: ArenaDescription) -> None:
        super().__init__(arena_description)
        self._previous_action: Action = Action.DO_NOTHING

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        super().decide(knowledge)
        desired_action = Action.TURN_RIGHT if self._previous_action == Action.ATTACK else Action.ATTACK
        self._previous_action = desired_action
        return desired_action


class CollectClosestWeaponStrategy(Strategy):
    def decide(self, knowledge: ChampionKnowledge) -> Optional[Action]:
        super().decide(knowledge)
        self._path = self.map_knowledge.get_closest_weapon_path(knowledge.position, 'axe', 'sword')
        return self._action_follow_path(knowledge)


class GoToMenhirStrategy(Strategy):
    def decide(self, knowledge: ChampionKnowledge) -> Optional[Action]:
        super().decide(knowledge)
        if self._path is None:
            self._path = self.map_knowledge.find_path(knowledge.position, self.map_knowledge.find_menhir())
        return self._action_follow_path(knowledge)


class RunAwayFromOpponentStrategy(Strategy):
    def __init__(self, arena_description: ArenaDescription, opponent_coords: Coords) -> None:
        super().__init__(arena_description)
        self._opponent_coords = opponent_coords

    def decide(self, knowledge: ChampionKnowledge) -> Optional[Action]:
        super().decide(knowledge)
        if self._path is None:
            run_destination = self._find_run_destination(knowledge.position)
            self._path = self.map_knowledge.find_path(knowledge.position, run_destination)
        return self._action_follow_path(knowledge)

    def _find_run_destination(self, position: Coords) -> Coords:
        x = min(self.map_knowledge.arena.size[0] - 1, max(0, position.x - (self._opponent_coords.x - position.x)))
        y = min(self.map_knowledge.arena.size[1] - 1, max(0, position.y - (self._opponent_coords.y - position.y)))

        for i in range(self.map_knowledge.arena.size[0]):
            for sign_x, sign_y in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
                new_x = min(self.map_knowledge.arena.size[0] - 1, max(0, x + i * sign_x))
                new_y = min(self.map_knowledge.arena.size[1] - 1, max(0, y + i * sign_y))
                run_destination = Coords(new_x, new_y)
                if self.map_knowledge.is_land(run_destination):
                    return run_destination
        raise RuntimeError("Could not find run destination")


class AttackOpponentStrategy(Strategy):
    def __init__(self, arena_description: ArenaDescription, opponent_coords: Coords) -> None:
        super().__init__(arena_description)
        self._opponent_coords = opponent_coords

    def decide(self, knowledge: ChampionKnowledge) -> Optional[Action]:
        super().decide(knowledge)
        if self.map_knowledge.can_attack(knowledge, self._opponent_coords):
            return Action.ATTACK

        desired_facing = self.map_knowledge.get_facing_for_attack(knowledge, self._opponent_coords)
        if desired_facing:
            current_facing = get_facing(knowledge)
            return determine_rotation_action(current_facing, desired_facing)

        self._path = self.map_knowledge.find_path(knowledge.position, self._opponent_coords)
        return self._action_follow_path(knowledge)
