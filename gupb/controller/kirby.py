import os.path
from typing import Callable

import numpy as np
import torch

from gupb.controller.kirby_learning import KirbyLearningController, MAP_PADDING, POLICIES_NUM
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import Facing
from gupb.model.tiles import TileDescription
from gupb.model.weapons import Knife

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
        my_position = tuple(knowledge.position)
        my_tile: TileDescription = knowledge.visible_tiles[knowledge.position]
        my_direction: Facing = my_tile.character.facing
        policies: list[Callable[[tuple[int, int], Facing], characters.Action]] = [
            self.travel,
            self.run,
            self.hide,
            self.attack,
            self.bigger_weapons,
            self.get_consumables,
        ]
        new_map, _ = self.analyse_knoledge(knowledge)

        with torch.no_grad():
            policy_b, expected_value_b = self.model_B(
                new_map.to(device)
            )  # przewidujemy przyszłość


        probs = policy_b.cpu().detach().numpy()[0]
        choice_idx = np.random.choice([i for i in range(POLICIES_NUM)], p=probs)

        self.time += 1
        self.actions[choice_idx] += 1
        self.prev_actions.append(choice_idx)

        return policies[choice_idx](my_position, my_direction)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        if os.path.exists("learned_weights.pth"):
            checkpoint = torch.load("learned_weights.pth", weights_only=False)
            self.model_A.load_state_dict(checkpoint["model"])
            self.model_B.load_state_dict(self.model_A.state_dict())
            self.optimizer.load_state_dict(checkpoint["optimizer"])

        arena = Arena.load(arena_description.name)
        self.terrain = arena.terrain

        self.map = torch.zeros(arena.size)
        self.transparent = torch.zeros(arena.size)
        self.seen = torch.zeros(arena.size)
        self.time = 0

        self.consumables = set()
        self.loot = {}
        self.effects = set()
        self.trees = []

        self.characters = {}
        self.characters_to_positions = {}
        self.positions_to_characters = {}

        for coords, tile in self.terrain.items():
            self.map[coords] += int(tile.passable)
            self.transparent[coords] += int(tile.transparent)

        self.mist = np.zeros_like(self.map)
        self.map = torch.tensor(
            np.pad(
                self.map,
                ((MAP_PADDING, MAP_PADDING), (MAP_PADDING, MAP_PADDING)),
                "constant",
                constant_values=(0, 0),
            )
        )

        self.transparent = torch.tensor(
            np.pad(
                self.transparent,
                ((MAP_PADDING, MAP_PADDING), (MAP_PADDING, MAP_PADDING)),
                "constant",
                constant_values=(0, 0),
            )
        )
        self.random_menhir()
        self.prev_map = None
        self.found_menhir = False
        self.prev_actions = []
        self.actions = np.zeros((POLICIES_NUM,))
        self.weapon = Knife().description()

    @property
    def name(self) -> str:
        return f"{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KIRBY


POTENTIAL_CONTROLLERS = [
    KirbyController("KirbyTest"),
]
