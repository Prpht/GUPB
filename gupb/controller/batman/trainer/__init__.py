import numpy as np

from torch import Tensor, nn, optim, no_grad
from torch.utils.data import DataLoader

from threading import Thread

from gupb.controller.batman.trainer.dataset import StateActionRewardDataset
from gupb.controller.batman.trainer.net import GuessRewardNet


class Trainer:
    def __init__(self, buffer_size: int = 1000, sample_limit: int = 250) -> None:
        self.reset_buffer()
        self._buffer_size = buffer_size
        self._sample_limit = sample_limit
        self._training_thread = None
        self._net = None
        self._training_end_forced = False

    def guess_reward(self, state: np.ndarray, params: np.ndarray):
        if self._net is None:
            return 0
        with no_grad():
            return self._net((Tensor(np.array([state])), Tensor(np.array([params]))))[
                0
            ].item()

    def reset_buffer(self):
        self._states = []
        self._params = []
        self._rewards = []

    def add_to_buffer(self, state: np.ndarray, params: np.ndarray, reward: float):
        if len(params) != 3:
            return  # it shouldn't happen

        self._states.append(state)
        self._params.append(params)
        self._rewards.append(reward)

        if len(self._states) > self._buffer_size:
            self._states.pop(0)
            self._params.pop(0)
            self._rewards.pop(0)

    def train(self):
        self.force_training_end()

        in_buffer = len(self._states)
        selected_indices = np.random.choice(
            in_buffer, min(in_buffer, self._sample_limit), replace=False
        )

        dataset = StateActionRewardDataset(
            Tensor(np.array(self._states)[selected_indices]),
            Tensor(np.array(self._params)[selected_indices]),
            Tensor(np.array(self._rewards)[selected_indices]),
        )

        dl = DataLoader(dataset, batch_size=32, shuffle=False)

        if self._net is None:
            self._net = GuessRewardNet(self._states[0].shape, self._params[0].shape[0])
            self._net.load()

        self._training_thread = Thread(target=self._training, args=(dl, 1))
        self._training_end_forced = False
        self._training_thread.start()

    def force_training_end(self):
        if self._training_thread is not None and self._training_thread.is_alive():
            self._training_end_forced = True
            self._training_thread.join()

    def _training(self, dl: DataLoader, epochs: int):
        if self._net is None:
            return

        loss_func = nn.MSELoss()
        optimizer = optim.Adam(self._net.parameters(), lr=0.001)

        losses = []

        for epoch in range(epochs):
            for X, y in dl:
                if self._training_end_forced:
                    break

                loss = loss_func(self._net(X).reshape(y.shape), y)
                losses.append(loss.item())

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        self._net.save()
