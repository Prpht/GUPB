from gupb.controller.aleph_aleph_zero.strategies.scouting_strategy import ScoutingStrategy
from gupb.controller.aleph_aleph_zero.shortest_path import build_graph, get_reachable, find_shortest_path
from gupb.controller.aleph_aleph_zero.strategies.strategy import Strategy, StrategyPriority
from gupb.controller.aleph_aleph_zero.strategies.travel_strategy import TravelStrategy
from gupb.model.characters import Action

weapons_score = {"knife": 1, "sword": 2, "amulet": 0, "axe": 4, "bow": 0, "bow_unloaded": 0, "bow_loaded": 0}


class WeaponRushStrategy(Strategy):

    def decide_and_proceed(self, knowledge, graph=None, map_knowledge=None, **kwargs):
        if map_knowledge is None:
            map_knowledge = knowledge

        if graph is None:
            graph = build_graph(knowledge)
        reachable = list(get_reachable(graph[(knowledge.position, knowledge.facing)]))

        current_weapon = knowledge.visible_tiles[knowledge.position].character.weapon.name
        weapons = []
        for coord in knowledge.visible_tiles:
            if knowledge.visible_tiles[coord].loot is not None and coord != knowledge.position:
                if weapons_score[knowledge.visible_tiles[coord].loot.name] > weapons_score[current_weapon]:
                    if coord in reachable:
                        weapons.append(coord)

        if len(weapons) == 0:
            for coord in map_knowledge.visible_tiles:
                if map_knowledge.visible_tiles[coord].loot is not None:
                    if weapons_score[map_knowledge.visible_tiles[coord].loot.name] > weapons_score[current_weapon]:
                        if coord in reachable:
                            weapons.append(coord)

        if len(weapons) == 0:
            return None, ScoutingStrategy(priority=StrategyPriority.IDLE)

        curr = graph[(knowledge.position, knowledge.facing)]

        weapons.sort(key=lambda x: len(find_shortest_path(curr, x)))

        travel_strategy = TravelStrategy(weapons[0], self)
        i=0
        while True:
            i+=1
            if i == 500:
                return Action.DO_NOTHING, self
            action, travel_strategy = travel_strategy.decide_and_proceed(knowledge, graph=graph, map_knowlege=map_knowledge, priority=self.priority)
            if action is not None:
                return action, self.get_more_important(travel_strategy)
