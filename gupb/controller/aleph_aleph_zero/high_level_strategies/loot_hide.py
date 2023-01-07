from gupb.controller.aleph_aleph_zero.config import EPOCH_TO_BE_IN_MELCHIR
from gupb.controller.aleph_aleph_zero.high_level_strategies.high_level_strategy import HighLevelStrategy
from gupb.controller.aleph_aleph_zero.shortest_path import find_shortest_path, get_closest_points
from gupb.controller.aleph_aleph_zero.strategies.guarding_strategy import GuardingStrategy
from gupb.controller.aleph_aleph_zero.strategies.menhir_rush_strategy import MenhirRushStrategy
from gupb.controller.aleph_aleph_zero.strategies.one_action_strategys import AttackStrategy, RunStrategy
from gupb.controller.aleph_aleph_zero.strategies.potion_rush_strategy import PotionRushStrategy
from gupb.controller.aleph_aleph_zero.strategies.scouting_strategy import ScoutingStrategy
from gupb.controller.aleph_aleph_zero.strategies.strategy import StrategyPriority
from gupb.controller.aleph_aleph_zero.strategies.travel_strategy import TravelStrategy
from gupb.controller.aleph_aleph_zero.strategies.weapon_rush_strategy import WeaponRushStrategy
from gupb.controller.aleph_aleph_zero.utils import if_character_to_kill
from gupb.model.characters import Action


class LootHide(HighLevelStrategy):
    def __init__(self, bot):
        super().__init__(bot)
        self.strategy = ScoutingStrategy(priority=StrategyPriority.IDLE)

    def decide(self):
        if self.bot.menhir_pos_updated or self.bot.menhir_seen:
            curr = self.bot.graph[(self.bot.knowledge.position, self.bot.knowledge.facing)]
            shortest_path = find_shortest_path(curr, self.bot.menhir_position)
            if (not self.bot.menhir_seen) or shortest_path is None or self.bot.epoch + len(
                    shortest_path) > EPOCH_TO_BE_IN_MELCHIR:
                self.bot.menhir_pos_updated = False
                self.strategy = self.strategy.get_more_important(
                    MenhirRushStrategy(self.bot.menhir_position, priority=StrategyPriority.TIME_SENSITIVE),
                    exception_signature="guarding menhir"
                )

            elif self.bot.menhir_seen:  # widzielismy juz menhira, znamy do niego droge i mamy duzo czasu
                if self.bot.knowledge.visible_tiles[self.bot.knowledge.position].character.weapon.name == "knife":
                    self.strategy = self.strategy.get_more_important(WeaponRushStrategy(StrategyPriority.PURPOSEFUL))
                else:
                    self.strategy = self.strategy.get_more_important(
                        PotionRushStrategy(StrategyPriority.PURPOSEFUL)
                    )

        i = 0  # quick fix
        while True:
            action, self.strategy = self.strategy.decide_and_proceed(self.bot.knowledge, graph=self.bot.graph,
                                                                     map_knowledge=self.bot.map_knowledge)
            i += 1
            if i == 20:
                return Action.TURN_LEFT
            if action is not None:
                return action