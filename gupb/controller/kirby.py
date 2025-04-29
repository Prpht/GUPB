import os.path

import numpy as np
import torch

from gupb.controller.kirby_learning import KirbyLearningController
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

device = "cuda" if torch.cuda.is_available() else "cpu"


class KirbyController(KirbyLearningController):
    def __init__(self, first_name: str = "Kirby"):
        super().__init__(first_name)
        if os.path.exists("best_weights.pth"):
            checkpoint = torch.load("best_weights.pth", weights_only=False)
            self.model_A.load_state_dict(checkpoint["model"])
            self.model_B.load_state_dict(checkpoint["model"])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KirbyController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        new_map, can_move_forward, attack_effects = self.analyse_knoledge(
            knowledge
        )
        with torch.no_grad():
            policy_B, predicted_value_B = self.model_B(new_map.to(device))

        choice_idx = np.random.choice(
            [0, 1, 2, 3],
            p=policy_B.cpu().detach().numpy()[0]
            if self.prev_map is not None
            else None,
        )

        self.time += 1

        return POSSIBLE_ACTIONS[choice_idx]

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        if game_no == 0:
            if os.path.exists("best_weights.pth"):
                checkpoint = torch.load("best_weights.pth", weights_only=False)
                self.model_A.load_state_dict(checkpoint["model"])
                self.model_B.load_state_dict(self.model_A.state_dict())
                self.optimizer.load_state_dict(checkpoint["optimizer"])

        arena = Arena.load(arena_description.name)
        self.terrain = arena.terrain

        self.map = torch.zeros(arena.size)
        self.seen = torch.zeros(arena.size)
        self.time = 0

        self.could_go_forward = True
        self.could_attack = True

        self.consumables: set = set()
        self.loot: set = set()
        self.effects: set = set()

        self.characters = {}
        self.characters_to_positions = {}
        self.positions_to_characters = {}

        self.menhir = (0, 0)

        for coords, tile in self.terrain.items():
            self.map[coords] += int(tile.passable)
        self.map = torch.tensor(
            np.pad(self.map, ((3, 3), (3, 3)), "constant", constant_values=(0, 0))
        )
        self.prev_map = None
        self.prev_action = None

    @property
    def name(self) -> str:
        return f"{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KIRBY


POTENTIAL_CONTROLLERS = [
    KirbyController("KirbyTest"),
]
