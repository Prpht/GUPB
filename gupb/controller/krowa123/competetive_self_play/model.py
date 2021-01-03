import numpy as np
import torch.nn as nn
import torch
import torch.nn.functional as F


class DQNet(nn.Module):

    def __init__(self, actions_number: int):
        super().__init__()
        self.__conv_1 = nn.Conv2d(
            in_channels=6, out_channels=32, kernel_size=5, padding=2
        )
        self.__pool_1 = nn.AvgPool2d(2, 2)  # 16x16
        self.__bn_1 = nn.BatchNorm2d(32)
        self.__conv_2 = nn.Conv2d(
            in_channels=32, out_channels=64, kernel_size=3, padding=1
        )
        self.__bn_2 = nn.BatchNorm2d(64)
        self.__conv_3 = nn.Conv2d(
            in_channels=64, out_channels=128, kernel_size=3, padding=1
        )
        self.__pool_2 = nn.AvgPool2d(2, 2)  # 8x8
        self.__bn_3 = nn.BatchNorm2d(128)
        self.__conv_4 = nn.Conv2d(
            in_channels=128, out_channels=256, kernel_size=3, padding=1
        )
        self.__pool_3 = nn.AvgPool2d(2, 2)  # 4x4
        self.__bn_4 = nn.BatchNorm2d(256)
        self.__conv_5 = nn.Conv2d(
            in_channels=256, out_channels=512, kernel_size=3, padding=1
        )
        self.__bn_5 = nn.BatchNorm2d(512)
        self.__pool_4 = nn.AvgPool2d(4, 4)
        self.__fc1 = nn.Linear(512, 256)
        self.__dropout = nn.Dropout(p=0.5)
        self.__fc2 = nn.Linear(256, 128)
        self.__advantage = nn.Linear(128, actions_number)
        self.__value = nn.Linear(128, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.__bn_1(self.__pool_1(F.relu(self.__conv_1(x))))
        x = self.__bn_2(F.relu(self.__conv_2(x)))
        x = self.__bn_3(self.__pool_2(F.relu(self.__conv_3(x))))
        x = self.__bn_4(self.__pool_3(F.relu(self.__conv_4(x))))
        x = self.__pool_4(self.__bn_5(F.relu(self.__conv_5(x))))
        x = self.__dropout(F.relu(self.__fc1(x.view((-1, 512)))))
        x = F.relu(self.__fc2(x))
        advantage = self.__advantage(x)
        state_value = self.__value(x)
        return state_value + (advantage - torch.mean(advantage))


if __name__ == '__main__':
    input_tensor = torch.Tensor(np.ones((1, 6, 32, 32), dtype=np.float32))
    network = DQNet(actions_number=4)
    result = network(input_tensor)
    print(result)
