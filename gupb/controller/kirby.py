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

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KirbyController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        new_map, _, _ = self.analyse_knoledge(knowledge)
        with torch.no_grad():
            predicted_health = self.critic_A(new_map.to(device))

        choice_idx = predicted_health[0].argmax()
        choice = POSSIBLE_ACTIONS[choice_idx]

        self.time += 1
        self.prev_map = new_map.clone()
        self.prev_action = choice_idx
        return choice

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        if game_no == 0:
            if os.path.exists("best_weights.pth"):
                checkpoint = torch.load("best_weights.pth", weights_only=True)
                self.critic_A.load_state_dict(checkpoint["model"])
                self.critic_B.load_state_dict(checkpoint["model"])

        arena = Arena.load(arena_description.name)
        terrain = arena.terrain

        self.map = torch.zeros(arena.size)
        self.seen = torch.zeros(arena.size)
        self.time = 0

        self.consumables: set = set()
        self.loot: set = set()
        self.effects: set = set()

        self.characters = {}
        self.characters_to_positions = {}
        self.positions_to_characters = {}

        self.menhir = (0, 0)

        for coords, tile in terrain.items():
            self.map[coords] += int(tile.passable)
        self.map = torch.tensor(np.pad(
            self.map, ((1, 1), (1, 1)), "constant", constant_values=(0, 0)
        ))
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
