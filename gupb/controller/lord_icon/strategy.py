from typing import NamedTuple
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.strategies.end_game_strategy import EndGameStrategy
from gupb.controller.lord_icon.strategies.explore_strategy import ExploreStrategy
from gupb.controller.lord_icon.strategies.camp_strategy import CampStrategy
from gupb.controller.lord_icon.strategies.kill_strategy import KillerStrategy
from gupb.controller.lord_icon.strategies.run_strategy import RunStrategy

from gupb.model.characters import Action


class ClassicStrategyController(NamedTuple):

    @staticmethod
    def decide(knowledge: Knowledge) -> Action:

        # Attack if you can
        for enemy in knowledge.enemies:
            if knowledge.character.can_attack(knowledge.map, enemy.position):
                return Action.ATTACK

        if knowledge.seen_mist and knowledge.menhir is not None:
            return EndGameStrategy.get_action(knowledge)

        for enemy in knowledge.enemies:
            if enemy.health < knowledge.character.health:
                return KillerStrategy.get_action(knowledge)

        if knowledge.seen_mist or knowledge.menhir is not None and knowledge.character.weapon != 'knife':
            # TO DO: Fix running away from mist
            return EndGameStrategy.get_action(knowledge)

        if knowledge.character.weapon == 'knife':
            return ExploreStrategy.get_action(knowledge)

        if not knowledge.enemies and knowledge.character.health < 3:
            return RunStrategy.get_action(knowledge)

        return KillerStrategy.get_action(knowledge)


class ShyStrategyController(NamedTuple):

    @staticmethod
    def decide(knowledge: Knowledge) -> Action:

        if knowledge.seen_mist and knowledge.menhir is not None:
            return EndGameStrategy.get_action(knowledge)

        return RunStrategy.get_action(knowledge)


class KillerStrategyController(NamedTuple):

    @staticmethod
    def decide(knowledge: Knowledge) -> Action:

        # Attack if you can
        for enemy in knowledge.enemies:
            if knowledge.character.can_attack(knowledge.map, enemy.position):
                return Action.ATTACK

        if knowledge.seen_mist and knowledge.menhir is not None:
            return EndGameStrategy.get_action(knowledge)

        for enemy in knowledge.enemies:
            if enemy.health <= knowledge.character.health:
                return KillerStrategy.get_action(knowledge)

        if knowledge.character.weapon == 'knife':
            return ExploreStrategy.get_action(knowledge)

        return KillerStrategy.get_action(knowledge)
