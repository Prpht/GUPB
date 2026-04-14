import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical
import numpy as np

INPUT_SIZE = 35
HIDDEN_SIZE = 256
NUM_ACTIONS = 8

ACTION_IDX = {
    0: 'TURN_LEFT',
    1: 'TURN_RIGHT',
    2: 'STEP_FORWARD',
    3: 'STEP_BACKWARD',
    4: 'STEP_LEFT',
    5: 'STEP_RIGHT',
    6: 'ATTACK',
    7: 'DO_NOTHING',
}


class ActorCritic(nn.Module):
    def __init__(self):
        super().__init__()

        self.shared = nn.Sequential(
            nn.Linear(INPUT_SIZE, HIDDEN_SIZE),
            nn.ReLU(),
            nn.Linear(HIDDEN_SIZE, HIDDEN_SIZE),
            nn.ReLU(),
        )

        # Aktor - co robić
        self.actor = nn.Sequential(
            nn.Linear(HIDDEN_SIZE, 64),
            nn.ReLU(),
            nn.Linear(64, NUM_ACTIONS),
        )

        # Krytyk - jak dobry jest stan
        self.critic = nn.Sequential(
            nn.Linear(HIDDEN_SIZE, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        shared = self.shared(x)
        logits = self.actor(shared)
        value = self.critic(shared)
        return logits, value

    def act(self, state_tensor, greedy=False):
        with torch.no_grad():
            logits, value = self.forward(state_tensor)
            
            # Penalizuj DO_NOTHING (index 7) bezpośrednio w logitach
            logits[:, 7] -= 5.0  # bardzo duża kara = prawie nigdy nie wybierze
            
            probs = F.softmax(logits, dim=-1)
            dist = Categorical(probs)
            if greedy:
                action = torch.argmax(probs, dim=-1)
            else:
                action = dist.sample()
            log_prob = dist.log_prob(action)
        return action.item(), log_prob.item(), value.item()

    def evaluate(self, states, actions):
        logits, values = self.forward(states)
        probs = F.softmax(logits, dim=-1)
        dist = Categorical(probs)
        log_probs = dist.log_prob(actions)
        entropy = dist.entropy()
        return log_probs, values.squeeze(-1), entropy