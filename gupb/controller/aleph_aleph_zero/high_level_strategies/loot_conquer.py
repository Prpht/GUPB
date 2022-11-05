from gupb.controller.aleph_aleph_zero.config import EPOCH_TO_BE_IN_MELCHIR
from gupb.controller.aleph_aleph_zero.high_level_strategies.high_level_strategy import HighLevelStrategy
from gupb.controller.aleph_aleph_zero.shortest_path import find_shortest_path, get_closest_points
from gupb.controller.aleph_aleph_zero.strategies.guarding_strategy import GuardingStrategy
from gupb.controller.aleph_aleph_zero.strategies.menhir_rush_strategy import MenhirRushStrategy
from gupb.controller.aleph_aleph_zero.strategies.one_action_strategys import AttackStrategy, RunStrategy
from gupb.controller.aleph_aleph_zero.strategies.scouting_strategy import ScoutingStrategy
from gupb.controller.aleph_aleph_zero.strategies.strategy import StrategyPriority
from gupb.controller.aleph_aleph_zero.strategies.travel_strategy import TravelStrategy
from gupb.controller.aleph_aleph_zero.strategies.weapon_rush_strategy import WeaponRushStrategy
from gupb.controller.aleph_aleph_zero.utils import if_character_to_kill
from gupb.model.characters import Action
from gupb.model.coordinates import Coords


class LootConquer(HighLevelStrategy):
    def __init__(self, bot):
        super().__init__(bot)
        self.strategy = ScoutingStrategy(priority=StrategyPriority.IDLE)

    def decide(self):
        if self.bot.knowledge.visible_tiles[self.bot.knowledge.position].character.weapon.name == "knife":
            self.strategy = self.strategy.get_more_important(WeaponRushStrategy(StrategyPriority.PURPOSEFUL))
        else:
            if self.bot.menhir_position is not None:
                self.strategy = self.strategy.get_more_important(
                    MenhirRushStrategy(self.bot.menhir_position, priority=StrategyPriority.PURPOSEFUL),
                    exception_signature="guarding menhir"
                )
            else:
                height_width = self.bot.height_width
                center = Coords(height_width[0]//2, height_width[1]//2)
                self.strategy = self.strategy.get_more_important(
                    MenhirRushStrategy(center, priority=StrategyPriority.IDLE),
                    exception_signature="guarding menhir"
                )

        i = 0  # quick fix
        while True:
            action, self.strategy = self.strategy.decide_and_proceed(self.bot.knowledge, graph=self.bot.graph,
                                                                     map_knowledge=self.bot.map_knowledge)
            i += 1
            if i == 20:
                return Action.DO_NOTHING
            if action is not None:
                return action