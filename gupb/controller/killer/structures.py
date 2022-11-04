from numpy import random


class Tree:
    def __init__(self, root_node: tuple):
        self.root_node = root_node
        self.edges = {}  # K - node to, V - node from (reversed order for easier path finding)
        self.marked_nodes = {}  # K - node value, V - list of nodes with given value

    def get_path(self, to_node: tuple):
        node = to_node
        if node in self.edges:
            path = []
            while node != self.root_node:
                path.append(node)
                node = self.edges[node]
            path.append(self.root_node)
            path.reverse()
            return path
        else:
            return None

    def append(self, node_from: tuple, node_to: tuple):
        self.edges[node_to] = node_from

    def mark_node(self, node, value):
        if value not in self.marked_nodes:
            self.marked_nodes[value] = []
        self.marked_nodes[value].append(node)

    def get_path_to_marked(self, value):
        if value in self.marked_nodes:
            return self.get_path(to_node=self.marked_nodes[value][0])
        else:
            return None

    def get_best_path(self, val_from, val_to):
        node_val = val_to
        while val_from <= node_val:
            path = self.get_path_to_marked(node_val)
            if path is not None:
                return path
            else:
                node_val -= 1
        nodes = list(self.edges.keys())
        random_node = nodes[random.choice(range(len(nodes)))]
        return self.get_path(to_node=random_node)
