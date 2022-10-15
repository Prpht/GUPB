from time import sleep

from gupb.controller.aleph_aleph_zero.shortest_path import build_graph, find_shortest_path
from gupb.controller.aleph_aleph_zero.strategy import Strategy, StrategyPriority
from gupb.model import characters
from gupb.model.coordinates import sub_coords, add_coords


class TravelStrategy(Strategy):
    def __init__(self, destination, proceeding_strategy, dodge=True, **kwargs):
        super().__init__(**kwargs)
        self.destination = destination
        self.proceeding_strategy = proceeding_strategy
        self.dodge = dodge

    def decide_and_proceed(self, knowledge, graph=None, map_knowledge=None, **kwargs):
        if graph is None:
            graph = build_graph(knowledge)
        if map_knowledge is None:
            map_knowledge = knowledge

        curr = graph[(knowledge.position, knowledge.facing)]
        shortest_path = find_shortest_path(curr, self.destination)
        if len(shortest_path) > 0 and shortest_path[0] in curr.connections.keys():
            next_action = curr.connections[shortest_path[0]]
            if next_action == characters.Action.STEP_FORWARD:
                two_ahead = None
                if knowledge.position + knowledge.facing.value + knowledge.facing.value in knowledge.visible_tiles.keys():
                    two_ahead = knowledge.visible_tiles[
                        knowledge.position + knowledge.facing.value + knowledge.facing.value]
                if self.dodge \
                        and two_ahead is not None \
                        and two_ahead.character is not None \
                        and two_ahead.character.facing not in {knowledge.facing, knowledge.facing.turn_left(), knowledge.facing.turn_right()}:
                    if (dodge_place := self._find_dodge_place(knowledge, map_knowledge)) is not None:
                        return None, TravelStrategy(dodge_place, self.proceeding_strategy, priority=StrategyPriority.CRITICAL)

            return next_action, self if len(shortest_path) > 1 else self.proceeding_strategy
        else:
            return None, self.proceeding_strategy

    def _find_free_spot(self, places, map_knowledge):
        for place in places:
            if place in map_knowledge.visible_tiles.keys() and (
                    map_knowledge.visible_tiles[place].type == "menhir" or map_knowledge.visible_tiles[
                    place].type == "land"):
                return place
        return None

    def _find_dodge_place(self, knowledge, map_knowledge):
        to_the_right = knowledge.facing.turn_right().value
        to_the_left = knowledge.facing.turn_left().value

        possible_dodges = [to_the_right, to_the_left]

        position = knowledge.position

        while position in map_knowledge.visible_tiles.keys():
            if (ret := self._find_free_spot([add_coords(dodge, position) for dodge in possible_dodges], map_knowledge)) is not None:
                return ret
            position = sub_coords(position, map_knowledge.facing.value)
        return None
