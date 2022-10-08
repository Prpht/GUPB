from time import sleep

from gupb.controller.AlephAlephZero.shortest_path import build_graph, find_shortest_path
from gupb.controller.AlephAlephZero.strategy import Strategy


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
            return next_action, self if len(shortest_path)>1 else self.proceeding_strategy
        else:
            return None, self.proceeding_strategy
