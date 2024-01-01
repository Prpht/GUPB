from torch import Tensor
from torch.utils.data import Dataset


class StateActionRewardDataset(Dataset):
    def __init__(self, states: list[Tensor], actions: Tensor, rewards: Tensor) -> None:
        self._states = states
        self._actions = actions
        self._rewards = rewards

    def __len__(self):
        return len(self._states)

    def __getitem__(self, index) -> tuple[tuple[Tensor, Tensor], Tensor]:
        return (self._states[index], self._actions[index]), self._rewards[index]
