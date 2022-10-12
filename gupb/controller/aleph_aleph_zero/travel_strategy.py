from time import sleep

from gupb.controller.aleph_aleph_zero.shortest_path import build_graph, find_shortest_path
from gupb.controller.aleph_aleph_zero.strategy import Strategy
from gupb.model import characters


class TravelStrategy(Strategy):
    def __init__(self, destination, proceeding_strategy):
        self.destination = destination
        self.proceeding_strategy = proceeding_strategy

    def decide_and_proceed(self, knowledge, graph=None, **kwargs):
        if graph is None:
            graph = build_graph(knowledge)
        curr = graph[(knowledge.position, knowledge.facing)]
        shortest_path = find_shortest_path(curr,self.destination)
        if len(shortest_path)>0 and shortest_path[0] in curr.connections.keys():
            next_action = curr.connections[shortest_path[0]]
            if next_action == characters.Action.STEP_FORWARD:
                two_ahead = knowledge.visible_tiles[knowledge.position + knowledge.facing.value + knowledge.facing.value]
                if two_ahead.character is not None and two_ahead.character.facing != knowledge.facing:
                    return characters.Action.TURN_RIGHT, self.proceeding_strategy #TODO nie wiem jak się powinien zachować

            return next_action, self if len(shortest_path)>1 else self.proceeding_strategy
        else:
            return None, self.proceeding_strategy
