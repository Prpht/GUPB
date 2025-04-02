import torch
import torch.nn as nn


class ResidualBlock(nn.Module):
    def __init__(self, in_channels, out_channels, stride=1):
        super().__init__()
        conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=stride, padding=1, bias=False)
        bn1 = nn.BatchNorm2d(out_channels)
        conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, stride=1, padding=1, bias=False)
        bn2 = nn.BatchNorm2d(out_channels)
        self.activation = nn.ReLU()
        self.main_sequence = nn.Sequential(conv1, bn1, self.activation, conv2, bn2)
        self.shortcut = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )

    def forward(self, x):
        out = self.main_sequence(x)
        out += self.shortcut(x)
        out = self.activation(out)
        return out


class Net(nn.Module):
    def __init__(self, num_classes=4):
        super().__init__()
        relu = nn.ReLU()
        sigmoid = nn.Sigmoid()
        conv1 = nn.Conv2d(3, 32, kernel_size=3, stride=1, padding=1, bias=False)
        bn1 = nn.BatchNorm2d(32)

        layer1 = self._make_layer(32, 64, stride=2)
        layer2 = self._make_layer(64, 128, stride=2)
        layer3 = self._make_layer(128, 256, stride=2)

        avg_pool = nn.AdaptiveAvgPool2d(1)
        flatten = nn.Flatten()
        fc = nn.Linear(256, num_classes)
        self.sequence = nn.Sequential(
            conv1, bn1, relu, layer1, layer2, layer3, avg_pool, flatten, fc,  # sigmoid
        )

    def _make_layer(self, in_channels, out_channels, stride):
        return nn.Sequential(
            ResidualBlock(in_channels, out_channels, stride),
            ResidualBlock(out_channels, out_channels, stride=1)
        )

    def forward(self, x) -> torch.Tensor:
        return self.sequence(x)


"""# Przykładowe wywołanie modelu
model = ResNet()
loss_fn = torch.nn.MSELoss()
x = torch.randn(1, 3, 32, 32)  # Przykładowy batch
print(x.dtype)
output = model(x)
print()

loss = loss_fn(torch.tensor(7, dtype=torch.float32), output.max())
loss.backward()"""
