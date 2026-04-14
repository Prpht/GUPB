import torch
import torch.nn as nn
import torch.nn.functional as F


class ResidualBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        residual = x
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.bn2(self.conv2(x))
        x += residual
        return F.relu(x)


class RepresentationNetwork(nn.Module):
    def __init__(self, input_channels, hidden_channels):
        super().__init__()
        self.conv = nn.Conv2d(
            input_channels,
            hidden_channels,
            kernel_size=3,
            padding=1,
            stride=1,
            bias=False,
        )
        self.bn = nn.BatchNorm2d(hidden_channels)
        self.resblocks = nn.Sequential(
            ResidualBlock(hidden_channels),
            ResidualBlock(hidden_channels),
            ResidualBlock(hidden_channels),
        )

    def forward(self, x):
        x = F.relu(self.bn(self.conv(x)))
        x = self.resblocks(x)
        return x


class DynamicsNetwork(nn.Module):
    def __init__(self, hidden_channels, action_space_size):
        super().__init__()
        # action is one-hot encoded and concatenated as planes
        self.conv = nn.Conv2d(
            hidden_channels + action_space_size,
            hidden_channels,
            kernel_size=3,
            padding=1,
            bias=False,
        )
        self.bn = nn.BatchNorm2d(hidden_channels)
        self.resblocks = nn.Sequential(
            ResidualBlock(hidden_channels),
            ResidualBlock(hidden_channels),
            ResidualBlock(hidden_channels),
        )
        self.reward_head = nn.Sequential(
            nn.Conv2d(hidden_channels, 1, kernel_size=1),
            nn.Flatten(),
            nn.Linear(
                8 * 8, 32
            ),  # Assuming 8x8 fixed size for simplicity, or adapt with GlobalAvgPool
            nn.ReLU(),
            nn.Linear(32, 1),
        )
        self.avg_pool = nn.AdaptiveAvgPool2d((8, 8))

    def forward(self, hidden_state, action_planes):
        x = torch.cat([hidden_state, action_planes], dim=1)
        x = F.relu(self.bn(self.conv(x)))
        next_hidden_state = self.resblocks(x)

        pooled = self.avg_pool(next_hidden_state)
        reward = self.reward_head(pooled)
        return next_hidden_state, reward


class PredictionNetwork(nn.Module):
    def __init__(self, hidden_channels, action_space_size):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d((8, 8))
        self.policy_head = nn.Sequential(
            nn.Conv2d(hidden_channels, 2, kernel_size=1),
            nn.BatchNorm2d(2),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(2 * 8 * 8, action_space_size),
        )
        self.value_head = nn.Sequential(
            nn.Conv2d(hidden_channels, 1, kernel_size=1),
            nn.BatchNorm2d(1),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(1 * 8 * 8, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, hidden_state):
        policy_logits = self.policy_head(self.avg_pool(hidden_state))
        value = self.value_head(self.avg_pool(hidden_state))
        return policy_logits, value


class DecoderNetwork(nn.Module):
    def __init__(self, hidden_channels, input_channels):
        super().__init__()
        self.resblocks = nn.Sequential(
            ResidualBlock(hidden_channels), ResidualBlock(hidden_channels)
        )
        self.deconv = nn.ConvTranspose2d(
            hidden_channels, input_channels, kernel_size=3, padding=1, stride=1
        )

    def forward(self, hidden_state):
        x = self.resblocks(hidden_state)
        x = self.deconv(x)
        return torch.sigmoid(x)  # Reconstructing binary channels


class SimSiamHead(nn.Module):
    def __init__(self, hidden_channels):
        super().__init__()
        dim = hidden_channels * 8 * 8
        self.avg_pool = nn.AdaptiveAvgPool2d((8, 8))
        self.projector = nn.Sequential(
            nn.Linear(dim, dim, bias=False),
            nn.BatchNorm1d(dim),
            nn.ReLU(inplace=True),
            nn.Linear(dim, dim, bias=False),
            nn.BatchNorm1d(dim, affine=False),
        )
        self.predictor = nn.Sequential(
            nn.Linear(dim, dim // 4, bias=False),
            nn.BatchNorm1d(dim // 4),
            nn.ReLU(inplace=True),
            nn.Linear(dim // 4, dim),
        )

    def forward(self, hidden_state):
        flat = self.avg_pool(hidden_state).view(hidden_state.size(0), -1)
        z = self.projector(flat)
        p = self.predictor(z)
        return z, p


class SyntaxTerrorNetwork(nn.Module):
    def __init__(self, input_channels=8, action_space_size=8, hidden_channels=32):
        super().__init__()
        self.representation = RepresentationNetwork(input_channels, hidden_channels)
        self.dynamics = DynamicsNetwork(hidden_channels, action_space_size)
        self.prediction = PredictionNetwork(hidden_channels, action_space_size)
        self.decoder = DecoderNetwork(hidden_channels, input_channels)
        self.simsiam = SimSiamHead(hidden_channels)
        self.hidden_channels = hidden_channels
        self.action_space_size = action_space_size

    def initial_inference(self, obs):
        hidden_state = self.representation(obs)
        policy_logits, value = self.prediction(hidden_state)
        return hidden_state, policy_logits, value

    def recurrent_inference(self, hidden_state, action):
        batch_size, _, h, w = hidden_state.shape
        action_planes = torch.zeros(
            batch_size, self.action_space_size, h, w, device=hidden_state.device
        )
        action_planes.scatter_(1, action.view(-1, 1, 1, 1).expand(-1, -1, h, w), 1.0)
        next_hidden_state, reward = self.dynamics(hidden_state, action_planes)
        policy_logits, value = self.prediction(next_hidden_state)
        return next_hidden_state, reward, policy_logits, value
