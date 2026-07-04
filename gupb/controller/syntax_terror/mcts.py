import math
import torch
import numpy as np

class MinMaxStats:
    """A class that holds the min-max values of the tree."""
    def __init__(self):
        self.maximum = -float('inf')
        self.minimum = float('inf')

    def update(self, value: float):
        self.maximum = max(self.maximum, value)
        self.minimum = min(self.minimum, value)

    def normalize(self, value: float) -> float:
        if self.maximum > self.minimum:
            # We normalize to [0, 1]
            return (value - self.minimum) / (self.maximum - self.minimum)
        return 0.5
    
class Node:
    def __init__(self, prior):
        self.visit_count = 0
        self.to_play = -1
        self.prior = prior
        self.value_sum = 0
        self.children = {}
        self.hidden_state = None
        self.reward = 0

    def expanded(self):
        return len(self.children) > 0

    def value(self):
        if self.visit_count == 0:
            return 0
        return self.value_sum / self.visit_count

    def expand(self, hidden_state, to_play, reward, policy_logits):
        self.hidden_state = hidden_state
        self.to_play = to_play
        self.reward = reward

        # softmax over logits
        policy_probs = torch.softmax(policy_logits, dim=1).squeeze(0).cpu().detach().numpy()
        for action, prob in enumerate(policy_probs):
            self.children[action] = Node(prob)

    def add_exploration_noise(self, dirichlet_alpha, exploration_fraction):
        actions = list(self.children.keys())
        noise = np.random.dirichlet([dirichlet_alpha] * len(actions))
        for a, n in zip(actions, noise):
            self.children[a].prior = self.children[a].prior * (1 - exploration_fraction) + n * exploration_fraction


class MCTS:
    def __init__(self, num_simulations, num_actions, discount=0.99, pb_c_init=1.25, pb_c_base=19652):
        self.num_simulations = num_simulations
        self.num_actions = num_actions
        self.discount = discount
        self.pb_c_init = pb_c_init
        self.pb_c_base = pb_c_base

    def run(self, network, obs):
        root = Node(0)
        min_max_stats = MinMaxStats()
        
        obs_tensor = torch.tensor(obs, dtype=torch.float32).unsqueeze(0)
        next_device = next(network.parameters()).device
        obs_tensor = obs_tensor.to(next_device)

        with torch.no_grad():
            hidden_state, policy_logits, value = network.initial_inference(obs_tensor)
            root.expand(hidden_state, 1, 0, policy_logits)
            root.add_exploration_noise(dirichlet_alpha=0.1, exploration_fraction=0.2)
        
        for _ in range(self.num_simulations):
            node = root
            search_path = [node]
            action_history = []

            # Selection
            while node.expanded():
                action, node = self.select_child(node, min_max_stats)
                search_path.append(node)
                action_history.append(action)

            # Expansion
            parent = search_path[-2]
            action = action_history[-1]
            
            with torch.no_grad():
                next_hidden_state, reward, policy_logits, value = network.recurrent_inference(
                    parent.hidden_state, torch.tensor([action], device=next_device)
                )
                node.expand(next_hidden_state, 1, reward.item(), policy_logits)

            # Backup
            self.backpropagate(search_path, value.item(), min_max_stats)

        policy = np.zeros(self.num_actions)
        for action, child in root.children.items():
            policy[action] = child.visit_count
        policy /= np.sum(policy)
        
        return policy, root.value()

    def select_child(self, node, min_max_stats):
        best_score = -float('inf')
        best_action = -1
        best_child = None

        for action, child in node.children.items():
            score = self.ucb_score(node, child, min_max_stats)
            if score > best_score:
                best_score = score
                best_action = action
                best_child = child

        return best_action, best_child

    def ucb_score(self, parent, child, min_max_stats):
        pb_c = math.log((parent.visit_count + self.pb_c_base + 1) / self.pb_c_base) + self.pb_c_init
        pb_c *= math.sqrt(parent.visit_count) / (child.visit_count + 1)

        prior_score = pb_c * child.prior
        value_score = child.value()

        if child.visit_count > 0:
            value_score = min_max_stats.normalize(child.value())
        else:
            value_score = min_max_stats.normalize(parent.value())
        
        return prior_score + value_score

    def backpropagate(self, search_path, value, min_max_stats):
        for node in reversed(search_path):
            node.value_sum += value
            node.visit_count += 1

            min_max_stats.update(node.value())

            value = node.reward + self.discount * value
