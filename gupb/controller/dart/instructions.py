from abc import ABC, abstractmethod
from typing import List, Optional
from gupb.controller.dart.movement_mechanics import MapKnowledge, determine_rotation_action, follow_path, get_facing, is_opponent_at_coords
from gupb.controller.dart.weapons import get_champion_weapon, get_weapon
from gupb.model.characters import Action, ChampionKnowledge
from gupb.model.coordinates import Coords


class Instruction(ABC):
    def __init__(self) -> None:
        super().__init__()
        self._path: Optional[List[Coords]] = None
        self._previous_position: Optional[Coords] = None

    @abstractmethod
    def decide(self, knowledge: ChampionKnowledge, map_knowledge: MapKnowledge) -> Optional[Action]:
        pass

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


class RotateAndAttackInstruction(Instruction):
    def __init__(self) -> None:
        super().__init__()
        self._previous_action: Action = Action.DO_NOTHING

    def decide(self, knowledge: ChampionKnowledge, map_knowledge: MapKnowledge) -> Action:
        desired_action = Action.TURN_RIGHT if self._previous_action == Action.ATTACK else Action.ATTACK
        self._previous_action = desired_action
        return desired_action


class CollectClosestWeaponInstruction(Instruction):
    def decide(self, knowledge: ChampionKnowledge, map_knowledge: MapKnowledge) -> Optional[Action]:
        if self._path and knowledge.position in self._path:
            return None
        self._path = map_knowledge.get_closest_weapon_path(knowledge.position, 'axe', 'sword', 'amulet', 'bow')
        return self._action_follow_path(knowledge)


class CollectClosestPotionInstruction(Instruction):
    def decide(self, knowledge: ChampionKnowledge, map_knowledge: MapKnowledge) -> Optional[Action]:
        if self._path and knowledge.position in self._path:
            return None
        self._path = map_knowledge.get_closest_consumable_path(knowledge.position, 'potion')
        return self._action_follow_path(knowledge)


class GoToMenhirInstruction(Instruction):
    def decide(self, knowledge: ChampionKnowledge, map_knowledge: MapKnowledge) -> Optional[Action]:
        weapon = get_weapon(get_champion_weapon(knowledge), map_knowledge.arena.terrain)
        opponents = list(map_knowledge.opponents.values())
        if weapon.is_any_opponent_in_range(knowledge, opponents):
            return Action.ATTACK
        self._path = map_knowledge.find_path(knowledge.position, map_knowledge.find_menhir())
        return self._action_follow_path(knowledge)


class RunAwayFromOpponentInstruction(Instruction):
    def __init__(self, opponent_coords: Coords) -> None:
        super().__init__()
        self._opponent_coords = opponent_coords

    def decide(self, knowledge: ChampionKnowledge, map_knowledge: MapKnowledge) -> Optional[Action]:
        if self._path is None:
            run_destination = self._find_run_destination(knowledge.position, map_knowledge)
            self._path = map_knowledge.find_path(knowledge.position, run_destination)
        return self._action_follow_path(knowledge)

    def _find_run_destination(self, position: Coords, map_knowledge: MapKnowledge) -> Coords:
        x = min(map_knowledge.arena.size[0] - 1, max(0, position.x - (self._opponent_coords.x - position.x)))
        y = min(map_knowledge.arena.size[1] - 1, max(0, position.y - (self._opponent_coords.y - position.y)))

        for i in range(map_knowledge.arena.size[0]):
            for sign_x, sign_y in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
                new_x = min(map_knowledge.arena.size[0] - 1, max(0, x + i * sign_x))
                new_y = min(map_knowledge.arena.size[1] - 1, max(0, y + i * sign_y))
                run_destination = Coords(new_x, new_y)
                if map_knowledge.is_land(run_destination):
                    return run_destination
        raise RuntimeError("Could not find run destination")


class AttackOpponentInstruction(Instruction):
    def __init__(self, opponent_coords: Coords) -> None:
        super().__init__()
        self._opponent_coords = opponent_coords

    def decide(self, knowledge: ChampionKnowledge, map_knowledge: MapKnowledge) -> Optional[Action]:
        weapon = get_weapon(get_champion_weapon(knowledge), map_knowledge.arena.terrain)

        if weapon.can_attack(knowledge, self._opponent_coords):
            return Action.ATTACK

        desired_facing = weapon.get_facing_for_attack(knowledge, self._opponent_coords)
        if desired_facing:
            current_facing = get_facing(knowledge)
            return determine_rotation_action(current_facing, desired_facing)

        attack_position = weapon.get_best_attack_position(knowledge, map_knowledge, self._opponent_coords)
        self._path = map_knowledge.find_path(knowledge.position, attack_position)
        return self._action_follow_path(knowledge)
