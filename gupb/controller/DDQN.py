import torch
import torch.nn as nn


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        relu = nn.ReLU()

        layer1 = nn.Linear(85, 255)
        layer2 = nn.Linear(255, 51)
        layer3 = nn.Linear(51, 4)
        # layer4 = nn.Linear(34, 4)
        layer5 = nn.Linear(192, 96)

        self.sequence = nn.Sequential(
            layer1, relu, layer2, relu, layer3
        )

    def forward(self, x) -> torch.Tensor:
        return self.sequence(x)
