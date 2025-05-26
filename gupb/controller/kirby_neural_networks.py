import torch.nn as nn
from torch.nn.utils import spectral_norm

DROPOUT_RATE = 0.5


class ActorCriticNet(nn.Module):
    def __init__(self, action_size, input_size=24, hidden1=2048, hidden2=1024, hidden3=256):
        super().__init__()
        self.actor = ActorNet(action_size=action_size, input_size=input_size, hidden1=hidden1, hidden2=hidden2, hidden3=hidden3)
        self.critic = CriticNet(input_size=input_size, hidden1=hidden1, hidden2=hidden2, hidden3=hidden3)

    def forward(self, x):
        policy = self.actor(x)
        value = self.critic(x)
        return policy, value


class CriticNet(nn.Module):
    def __init__(self, input_size=24, hidden1=2048, hidden2=1024, hidden3=256):
        super().__init__()
        self.shared = nn.Sequential(
            spectral_norm(nn.Linear(input_size, hidden1)),
            nn.ReLU(),
            nn.LayerNorm(hidden1),
            spectral_norm(nn.Linear(hidden1, hidden2)),
            nn.ReLU(),
            nn.LayerNorm(hidden2),
            spectral_norm(nn.Linear(hidden2, hidden3)),
            nn.ReLU(),
            nn.LayerNorm(hidden3),
        )
        self.critic_head = nn.Linear(hidden3, 1)

    def forward(self, x):
        shared_out = self.shared(x)
        value = self.critic_head(shared_out)
        return value


class ActorNet(nn.Module):
    def __init__(self, action_size, input_size=24, hidden1=2048, hidden2=1024, hidden3=256):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(input_size, hidden1),
            nn.ReLU(),
            nn.Dropout(p=DROPOUT_RATE),
            nn.LayerNorm(hidden1),
            nn.Linear(hidden1, hidden2),
            nn.ReLU(),
            nn.Dropout(p=DROPOUT_RATE),
            nn.LayerNorm(hidden2),
            nn.Linear(hidden2, hidden3),
            nn.ReLU(),
            nn.Dropout(p=DROPOUT_RATE),
            nn.LayerNorm(hidden3),
        )
        self.actor_head = nn.Sequential(
            nn.Linear(hidden3, action_size), nn.Softmax(dim=-1)
        )

    def forward(self, x):
        shared_out = self.shared(x)
        policy = self.actor_head(shared_out)
        return policy


class ActorLoss(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, advantages, log_prob):
        return (-advantages * log_prob).mean()
