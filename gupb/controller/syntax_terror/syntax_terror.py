from datetime import datetime

import numpy as np
import torch

from gupb.controller import Controller
from gupb.model import arenas, characters

from .mcts import MCTS
from .network import SyntaxTerrorNetwork
from .wrapper import GUPBWrapper

ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.ATTACK,
    characters.Action.DO_NOTHING,
]


class SyntaxTerror(Controller):
    def __init__(
        self,
        bot_name: str,
        network=None,
        weights: str = "gupb/controller/syntax_terror/syntax_terror_v2.pth",
    ):
        self.bot_name = bot_name
        self.wrapper = GUPBWrapper()
        self.mcts = MCTS(num_simulations=10, num_actions=len(ACTIONS))

        device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "mps" if torch.backends.mps.is_available() else "cpu"
        )

        state_dict = torch.load(weights, map_location=device)
        hidden_channels = state_dict["representation.conv.weight"].shape[0]
        self.network = SyntaxTerrorNetwork(hidden_channels=hidden_channels)
        self.network.load_state_dict(state_dict)
        self.network.to(device)
        self.network.eval()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SyntaxTerror):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    @property
    def name(self) -> str:
        return f"{self.bot_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BLUE

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        pass

    def praise(self, score: int) -> None:
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:

        obs = self.wrapper.encode(knowledge)

        self.network.eval()
        policy, _ = self.mcts.run(self.network, obs)

        action_idx = np.argmax(policy)

        return ACTIONS[action_idx]
