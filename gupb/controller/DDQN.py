import torch
import torch.nn as nn


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        relu = nn.ReLU()

        layer1 = nn.Linear(111, 444)
        layer2 = nn.Linear(444, 148)
        layer3 = nn.Linear(148, 4)
        layer4 = nn.Linear(384, 192)
        layer5 = nn.Linear(192, 96)
        layer6 = nn.Linear(96, 64)
        layer7 = nn.Linear(64, 32)

        self.sequence = nn.Sequential(
            layer1, relu, layer2, relu, layer3
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
