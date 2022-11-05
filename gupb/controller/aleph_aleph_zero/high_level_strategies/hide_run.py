from gupb.controller.aleph_aleph_zero.config import EPOCH_TO_BE_IN_MELCHIR
from gupb.controller.aleph_aleph_zero.high_level_strategies.high_level_strategy import HighLevelStrategy
from gupb.controller.aleph_aleph_zero.shortest_path import find_shortest_path, get_closest_points, get_reachable
from gupb.controller.aleph_aleph_zero.strategies.guarding_strategy import GuardingStrategy
from gupb.controller.aleph_aleph_zero.strategies.menhir_rush_strategy import MenhirRushStrategy
from gupb.controller.aleph_aleph_zero.strategies.one_action_strategys import AttackStrategy, RunStrategy
from gupb.controller.aleph_aleph_zero.strategies.scouting_strategy import ScoutingStrategy
from gupb.controller.aleph_aleph_zero.strategies.strategy import StrategyPriority
from gupb.controller.aleph_aleph_zero.strategies.travel_strategy import TravelStrategy
from gupb.controller.aleph_aleph_zero.strategies.weapon_rush_strategy import WeaponRushStrategy
from gupb.controller.aleph_aleph_zero.utils import if_character_to_kill, taxicab_distance
from gupb.model.characters import Action
from gupb.model.coordinates import Coords


class HideRun(HighLevelStrategy):
    def __init__(self, bot):
        super().__init__(bot)
        self.strategy = ScoutingStrategy(priority=StrategyPriority.IDLE)

    def decide(self):
        menhir_pos = self.bot.menhir_position
        if menhir_pos is None:
            height_width = self.bot.height_width
            menhir_pos = Coords(height_width[0] // 2, height_width[1] // 2)

        reachable = list(get_reachable(self.bot.graph[(self.bot.knowledge.position, self.bot.knowledge.facing)]))
        reachable.sort(key=lambda x: taxicab_distance(x, menhir_pos))
        menhir_pos = reachable[0]

        curr = self.bot.graph[(self.bot.knowledge.position, self.bot.knowledge.facing)]
        shortest_path = find_shortest_path(curr, menhir_pos)
        if self.bot.epoch + len(shortest_path) > EPOCH_TO_BE_IN_MELCHIR:
            self.bot.menhir_pos_updated = False
            self.strategy = self.strategy.get_more_important(
                MenhirRushStrategy(menhir_pos, priority=StrategyPriority.TIME_SENSITIVE),
                exception_signature="guarding menhir"
            )
        else:
            self.strategy = self.strategy.get_more_important(
                TravelStrategy(
                    get_closest_points(self.bot.save_spots, self.bot.graph,
                                       self.bot.graph[self.bot.knowledge.position, self.bot.knowledge.facing])[0],
                    GuardingStrategy(priority=StrategyPriority.PURPOSEFUL, signature="guarding safespot"),
                    priority=StrategyPriority.PURPOSEFUL
                ),
                exception_signature="guarding safespot"
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