import torch
import torch.nn as nn


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        relu = nn.LeakyReLU()

        layer1 = nn.Linear(83, 300)
        layer2 = nn.Linear(300, 100)
        layer3 = nn.Linear(100, 4)
        # layer4 = nn.Linear(34, 4)
        layer5 = nn.Linear(192, 96)

        self.sequence = nn.Sequential(
            layer1, relu, layer2, relu, layer3
        )

    def forward(self, x) -> torch.Tensor:
        return self.sequence(x)
