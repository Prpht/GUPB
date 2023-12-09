from torch import Tensor, nn, ones, cat, save, load


PATH_TO_MODEL = "./gupb/controller/batman/trainer/net"


class GetValueNet(nn.Module):
    def __init__(self, state_shape: tuple[int], n_actions: int) -> None:
        super(GetValueNet, self).__init__()

        if len(state_shape) == 1:
            self._feature_extractor = nn.Identity()
        elif len(state_shape) == 3:
            self._feature_extractor = nn.Sequential(
                nn.Conv2d(state_shape[0], 3, 4),
                nn.ReLU(),
                nn.Conv2d(4, 8, 3),
                nn.ReLU(),
                nn.Conv2d(8, 16, 3, stride=2),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d(16),
            )

        n_features = self._feature_extractor(ones((1, *state_shape))).shape[1]

        self._fc = nn.Sequential(
            nn.Linear(n_features + n_actions, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.ReLU(),
        )

    def forward(self, state_acton: tuple[Tensor, Tensor]) -> Tensor:
        state, action = state_acton
        features = self._feature_extractor(state)
        X = cat((features, action), dim=1)
        return self._fc(X)

    def try_load(self):
        try:
            self.load_state_dict(load(PATH_TO_MODEL))
        except:
            pass

    def save(self):
        save(self.state_dict(), PATH_TO_MODEL)
        save(self._feature_extractor.state_dict(), f"{PATH_TO_MODEL}_cnn")
