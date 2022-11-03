from typing import Optional, Protocol, Type
from gupb.controller.dart.instructions import AttackOpponentInstruction, CollectClosestWeaponInstruction, GoToMenhirInstruction, Instruction, RotateAndAttackInstruction, RunAwayFromOpponentInstruction
from gupb.controller.dart.movement_mechanics import MapKnowledge, euclidean_distance, get_champion_weapon, is_opponent_at_coords
from gupb.model.characters import Action, ChampionKnowledge
from gupb.model.coordinates import Coords


class Strategy(Protocol):
    def decide(self, knowledge: ChampionKnowledge, map_knowledge: MapKnowledge) -> Action:
        ...


class DefaultStrategy:
    def __init__(self) -> None:
        self._instruction: Instruction = CollectClosestWeaponInstruction()
        self._previous_opponent_coords: Optional[Coords] = None

    def decide(self, knowledge: ChampionKnowledge, map_knowledge: MapKnowledge) -> Action:
        # Handle mist observed
        if map_knowledge.closest_mist_coords and not map_knowledge.find_menhir() == knowledge.position:
            self._instruction = GoToMenhirInstruction()

        # Handle opponent found
        elif self._handle_opponent_instruction(knowledge, map_knowledge):
            self._instruction = self._handle_opponent_instruction(knowledge, map_knowledge)

        action = self._instruction.decide(knowledge, map_knowledge)
        if action:
            return action

        # Handle collect weapon
        if get_champion_weapon(knowledge) == "knife":
            self._instruction = CollectClosestWeaponInstruction()

        # Default
        elif not self._is_same_instruction(RotateAndAttackInstruction):
            self._instruction = RotateAndAttackInstruction()

        return self._instruction.decide(knowledge, map_knowledge)

    def _handle_opponent_instruction(self, knowledge: ChampionKnowledge,
                                     map_knowledge: MapKnowledge) -> Optional[Instruction]:
        # Opponent has moved
        if self._previous_opponent_coords in knowledge.visible_tiles and not is_opponent_at_coords(
                self._previous_opponent_coords, knowledge.visible_tiles):
            self._previous_opponent_coords = None
        # Find all opponents
        opponents_coords = list(map_knowledge.opponents.values())
        if self._previous_opponent_coords:
            opponents_coords.append(self._previous_opponent_coords)
        # No opponents
        if not opponents_coords:
            return None
        # Decide
        opponent_coords = map_knowledge.find_closest_coords(knowledge.position, opponents_coords)
        if euclidean_distance(knowledge.position, opponent_coords) < 3:
            self._previous_opponent_coords = opponent_coords
            return AttackOpponentInstruction(opponent_coords)
        elif not self._is_same_instruction(RunAwayFromOpponentInstruction) and euclidean_distance(knowledge.position, opponent_coords) < 5:
            return RunAwayFromOpponentInstruction(opponent_coords)
        return None

    def _is_same_instruction(self, strategy_class: Type[Instruction]) -> bool:
        return self._instruction.__class__.__name__ == strategy_class.__name__


class PassivePassiveStrategy(DefaultStrategy):
    def _handle_opponent_instruction(self, knowledge: ChampionKnowledge,
                                     map_knowledge: MapKnowledge) -> Optional[Instruction]:
        # Opponent has moved
        if self._previous_opponent_coords in knowledge.visible_tiles and not is_opponent_at_coords(
                self._previous_opponent_coords, knowledge.visible_tiles):
            self._previous_opponent_coords = None
        # Find all opponents
        opponents_coords = list(map_knowledge.opponents.values())
        if self._previous_opponent_coords:
            opponents_coords.append(self._previous_opponent_coords)
        # No opponents
        if not opponents_coords:
            return None
        # Decide
        opponent_coords = map_knowledge.find_closest_coords(knowledge.position, opponents_coords)
        if not self._is_same_instruction(RunAwayFromOpponentInstruction) and euclidean_distance(
                knowledge.position, opponent_coords) < 5:
            return RunAwayFromOpponentInstruction(opponent_coords)
        return None


class AgressiveAgressiveStrategy(DefaultStrategy):
    def _handle_opponent_instruction(self, knowledge: ChampionKnowledge,
                                     map_knowledge: MapKnowledge) -> Optional[Instruction]:
        # Opponent has moved
        if self._previous_opponent_coords in knowledge.visible_tiles and not is_opponent_at_coords(
                self._previous_opponent_coords, knowledge.visible_tiles):
            self._previous_opponent_coords = None
        # Find all opponents
        opponents_coords = list(map_knowledge.opponents.values())
        if self._previous_opponent_coords:
            opponents_coords.append(self._previous_opponent_coords)
        # No opponents
        if not opponents_coords:
            return None
        # Decide
        opponent_coords = map_knowledge.find_closest_coords(knowledge.position, opponents_coords)
        return AttackOpponentInstruction(opponent_coords)


class PassiveAgressiveStrategy(DefaultStrategy):
    def _handle_opponent_instruction(self, knowledge: ChampionKnowledge,
                                     map_knowledge: MapKnowledge) -> Optional[Instruction]:
        # Opponent has moved
        if self._previous_opponent_coords in knowledge.visible_tiles and not is_opponent_at_coords(
                self._previous_opponent_coords, knowledge.visible_tiles):
            self._previous_opponent_coords = None
        # Find all opponents
        opponents_coords = list(map_knowledge.opponents.values())
        if self._previous_opponent_coords:
            opponents_coords.append(self._previous_opponent_coords)
        # No opponents
        if not opponents_coords:
            return None
        # Decide
        opponent_coords = map_knowledge.find_closest_coords(knowledge.position, opponents_coords)
        if get_champion_weapon(knowledge) != "knife":
            return AttackOpponentInstruction(opponent_coords)
        if not self._is_same_instruction(RunAwayFromOpponentInstruction) and euclidean_distance(
                knowledge.position, opponent_coords) < 5:
            return RunAwayFromOpponentInstruction(opponent_coords)
        return None


class AgressivePassiveStrategy(DefaultStrategy):
    def _handle_opponent_instruction(self, knowledge: ChampionKnowledge,
                                     map_knowledge: MapKnowledge) -> Optional[Instruction]:
        # Opponent has moved
        if self._previous_opponent_coords in knowledge.visible_tiles and not is_opponent_at_coords(
                self._previous_opponent_coords, knowledge.visible_tiles):
            self._previous_opponent_coords = None
        # Find all opponents
        opponents_coords = list(map_knowledge.opponents.values())
        if self._previous_opponent_coords:
            opponents_coords.append(self._previous_opponent_coords)
        # No opponents
        if not opponents_coords:
            return None
        # Decide
        opponent_coords = map_knowledge.find_closest_coords(knowledge.position, opponents_coords)
        if get_champion_weapon(knowledge) == "knife":
            return AttackOpponentInstruction(opponent_coords)
        if not self._is_same_instruction(RunAwayFromOpponentInstruction) and euclidean_distance(
                knowledge.position, opponent_coords) < 5:
            return RunAwayFromOpponentInstruction(opponent_coords)
        return None


POSSIBLE_STRATEGIES = [
    AgressiveAgressiveStrategy,
    PassivePassiveStrategy,
    PassiveAgressiveStrategy,
    AgressivePassiveStrategy
]
