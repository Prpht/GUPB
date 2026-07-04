import numpy as np

from .feature_extractor import FEATURE_DIM


class FeedForwardNetwork:
    def __init__(
        self,
        weights: list[np.ndarray],
        biases: list[np.ndarray],
        activation: str = "tanh",
    ):
        self.weights = weights
        self.biases = biases
        self.activation = activation

    def activate(self, features: np.ndarray) -> np.ndarray:
        x = np.asarray(features, dtype=np.float32)
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            x = x @ w + b
            if i < len(self.weights) - 1:
                if self.activation == "tanh":
                    x = np.tanh(x)
                elif self.activation == "relu":
                    x = np.maximum(0.0, x)
        return x


class PolicyModel:
    def __init__(self, net: FeedForwardNetwork):
        self.net = net

    def predict(self, features: np.ndarray) -> np.ndarray:
        if features.shape[0] != FEATURE_DIM:
            raise ValueError(
                f"Expected {FEATURE_DIM} features, got {features.shape[0]}"
            )
        return np.asarray(self.net.activate(features), dtype=np.float32)
