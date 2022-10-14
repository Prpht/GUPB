from abc import ABC, abstractmethod
from enum import Enum, auto
import random
from typing import List, Optional, Tuple
from gupb.controller.dart.movement_mechanics import MapKnowledge, determine_action, euclidean_distance, find_opponents, follow_path, get_champion_weapon, get_facing, is_opponent_in_front
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

    def _action_follow_path(self, knowledge: ChampionKnowledge) -> Action:
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

    def _action_attack_opponent(self, knowledge: ChampionKnowledge, opponent_coords: Coords) -> Action:
        if self._map_knowledge.can_attack(knowledge, opponent_coords):
            return Action.ATTACK
        desired_facing = self._map_knowledge.get_facing_for_attack(knowledge, opponent_coords)
        if desired_facing:
            current_facing = get_facing(knowledge)
            return determine_action(current_facing, desired_facing)
        self._path = self._map_knowledge.find_path(knowledge.position, opponent_coords)
        return self._action_follow_path(knowledge)

    def _action_run_away(self, knowledge: ChampionKnowledge, opponent_coords: Coords) -> Action:
        x = min(self._map_knowledge.arena.size[0]-1, max(
            0, knowledge.position.x - (opponent_coords.x - knowledge.position.x)))
        y = min(self._map_knowledge.arena.size[1]-1, max(
            0, knowledge.position.y - (opponent_coords.y - knowledge.position.y)))

        for i in range(self._map_knowledge.arena.size[0]):
            for sign_x, sign_y in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
                run_destination = Coords(x+i*sign_x, y+i*sign_y)
                if self._map_knowledge.is_land(run_destination):
                    self._path = self._map_knowledge.find_path(knowledge.position, run_destination)
                    return self._action_follow_path(knowledge)
        return random.choice(POSSIBLE_ACTIONS)


class AxeAndCenterStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__()
        self._state = Steps.init
        self._previous_action: Action = Action.DO_NOTHING
        self._opponent: Optional[Tuple[Coords, str]] = None
        self._mode = Mode.run_away

    def reset(self, arena_description: ArenaDescription) -> None:
        self._state = Steps.init
        self._previous_action = Action.DO_NOTHING
        self._opponent = None
        self._mode = Mode.run_away
        return super().reset(arena_description)

    def praise(self, score: int) -> None:
        ...

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self._map_knowledge.update_weapons_positions()

        # Handle opponent found
        opponents = find_opponents(knowledge.visible_tiles)
        if opponents:
            opponents_coords = list(opponents.keys())
            if self._opponent:
                opponents_coords.append(self._opponent[0])
            opponent_coords = self._map_knowledge.find_closest_coords(knowledge.position, opponents_coords)
            if euclidean_distance(knowledge.position, opponent_coords) < 3:
                if self._mode == Mode.run_away:
                    return self._action_run_away(knowledge, opponent_coords)
                return self._action_attack_opponent(knowledge, opponent_coords)

        # Handle mist found
        mist_coords = self._map_knowledge.find_mist_coords(knowledge)
        if mist_coords:
            self._path = self._map_knowledge.find_path(knowledge.position, self._map_knowledge.find_middle_cords())
            self._mode = Mode.attack

        if not self._path:
            if self._state == Steps.init:
                if get_champion_weapon(knowledge) != "knife":
                    self._state = Steps.weapon_found
                    self._mode = Mode.attack
                    return self._action_rotate_and_attack()
                self._path = self._map_knowledge.get_closest_weapon_path(knowledge.position, 'axe', 'sword')
            elif self._state == Steps.weapon_found:
                return self._action_rotate_and_attack()

        return self._action_follow_path(knowledge) if self._path else self._action_rotate_and_attack()

    def _action_rotate_and_attack(self) -> Action:
        desired_action = Action.TURN_RIGHT if self._previous_action == Action.ATTACK else Action.ATTACK
        self._previous_action = desired_action
        return desired_action
