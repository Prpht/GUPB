import logging
import pathlib
from datetime import datetime

import numpy as np
import torch

from gupb.controller import Controller
from gupb.model import arenas, characters, coordinates
from gupb.model.characters import Facing

from .mcts import MCTS
from .network import MuZeroNetwork
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

OBS_CHANNELS = [
    "Obstacles",
    "Own position",
    "Visible enemies",
    "Weapons",
    "Consumables",
    "Facing direction",
    "Effects",
    "Char weapons",
]

REWARDS_SCALING = {
    "base_penalty": -0.05,
    "no_movement_penalty": -0.05,
    "stand_in_mist_penalty": -1.0,
    "stand_in_fire_penalty": -2.0,
    "stand_in_cut_penalty": -3.0,
    "menhir_away_penalty": -0.1,
    "menhir_closer_reward": 0.1,
    "exploration_reward": 0.5,
    "tactical_attack_reward": 0.5,
    "enemy_seen_reward": 0.1,
    "weapon_pickup_reward": 0.5,
    "health_up_reward": 1.0,
    "health_down_penalty": -1.0,
    "mid_rewards_multiplier": 2.0,
    "final_score_multiplier": 15.0,
}

knowledge_logger = logging.getLogger("knowledge")


def configure_logging(log_directory: str) -> None:
    logging_dir_path = pathlib.Path(log_directory)
    logging_dir_path.mkdir(parents=True, exist_ok=True)
    logging_dir_path.chmod(0o777)
    time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    knowledge_logger.propagate = False
    if not knowledge_logger.handlers:
        knowledge_file_path = logging_dir_path / f"gupb_kno__{time}.log"
        knowledge_file_handler = logging.FileHandler(knowledge_file_path.as_posix())
        verbose_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(module)s.%(funcName)s:%(lineno)d | %(message)s"
        )
        knowledge_file_handler.setFormatter(verbose_formatter)
        knowledge_logger.addHandler(knowledge_file_handler)
        knowledge_logger.setLevel(logging.INFO)


class SyntaxTerror(Controller):
    def __init__(
        self,
        bot_name: str,
        network=None,
        is_training: bool = False,
        rewards_scaling: dict = None,  # type: ignore
    ):
        self.bot_name = bot_name
        self.wrapper = GUPBWrapper()
        if network is None:
            self.network = MuZeroNetwork(
                input_channels=8, action_space_size=len(ACTIONS), hidden_channels=32
            )
            self.network.eval()
        else:
            self.network = network

        self.mcts = MCTS(num_simulations=10, num_actions=len(ACTIONS))
        self.is_training = is_training
        if rewards_scaling:
            self.rewards_scaling = rewards_scaling
        else:
            self.rewards_scaling = REWARDS_SCALING

        self.trajectory = []
        self.last_obs = None
        self.last_action_idx = None
        self.last_policy = None
        self.last_value = None
        self.last_health = characters.CHAMPION_STARTING_HP
        self.weapon_name = "knife"
        self.visited_tiles = set()
        self.menhir_position = None
        self.last_menhir_dist = None
        self.last_game_score = 0.0
        self.last_tile = None
        self.terminal_indices = []

        # configure_logging("mu_log")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SyntaxTerror):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    def get_weapon_hit_area(
        self, position: coordinates.Coords, facing: Facing, weapon_name: str, knowledge
    ) -> list[coordinates.Coords]:
        hit_tiles = []

        base_weapon = weapon_name.split("_")[0]

        if base_weapon in ["knife", "scroll", "sword", "bow"]:
            reach = {"knife": 1, "scroll": 1, "sword": 3, "bow": 50}[base_weapon]
            curr_pos = position
            for _ in range(reach):
                curr_pos = curr_pos + facing.value

                if curr_pos not in knowledge.visible_tiles:
                    break

                hit_tiles.append(curr_pos)

                if knowledge.visible_tiles[curr_pos].type in ["wall", "sea"]:
                    break

        elif base_weapon == "axe":
            center = position + facing.value
            left = center + facing.turn_left().value
            right = center + facing.turn_right().value
            hit_tiles.extend([left, center, right])

        elif base_weapon == "amulet":
            hit_tiles.extend(
                [
                    position + (1, 1),
                    position + (-1, 1),
                    position + (1, -1),
                    position + (-1, -1),
                    position + (2, 2),
                    position + (-2, 2),
                    position + (2, -2),
                    position + (-2, -2),
                ]
            )

        return hit_tiles

    def calculate_reward(self, knowledge: characters.ChampionKnowledge) -> float:
        """Calculates the shaped reward for the current turn."""

        reward = 0

        if not self.menhir_position:
            for coords, tile_desc in knowledge.visible_tiles.items():
                if tile_desc.type == "menhir":
                    self.menhir_position = coords
                    break

        reward += self.rewards_scaling["base_penalty"]

        current_tile = knowledge.visible_tiles.get(knowledge.position)
        if not current_tile:
            return reward

        if self.last_tile and knowledge.position == self.last_tile:
            reward += self.rewards_scaling["no_movement_penalty"]
        self.last_tile = knowledge.position

        if knowledge.position not in self.visited_tiles:
            reward += self.rewards_scaling["exploration_reward"]
            self.visited_tiles.add(knowledge.position)

        if current_tile.effects:
            if any(effect.type == "mist" for effect in current_tile.effects):
                reward += self.rewards_scaling["stand_in_mist_penalty"]
            elif any(effect.type == "fire" for effect in current_tile.effects):
                reward += self.rewards_scaling["stand_in_fire_penalty"]
            elif any(effect.type == "weaponcut" for effect in current_tile.effects):
                reward += self.rewards_scaling["stand_in_cut_penalty"]

        if self.menhir_position:
            current_dist = abs(knowledge.position[0] - self.menhir_position[0]) + abs(
                knowledge.position[1] - self.menhir_position[1]
            )
            if self.last_menhir_dist is not None:
                if current_dist < self.last_menhir_dist:
                    reward += self.rewards_scaling["menhir_closer_reward"]
                elif current_dist > self.last_menhir_dist:
                    reward += self.rewards_scaling["menhir_away_penalty"]
            self.last_menhir_dist = current_dist

        if current_tile and current_tile.character:
            current_health = current_tile.character.health
            current_weapon = current_tile.character.weapon.name
            current_facing = current_tile.character.facing

            if (
                self.last_action_idx is not None
                and ACTIONS[self.last_action_idx] == characters.Action.ATTACK
            ):
                attack_tiles = self.get_weapon_hit_area(
                    knowledge.position, current_facing, current_weapon, knowledge
                )
                for tile_pos in attack_tiles:
                    if tile_pos in knowledge.visible_tiles:
                        target_tile = knowledge.visible_tiles[tile_pos]
                        if (
                            target_tile.character
                            and target_tile.character.controller_name != self.name
                        ):
                            reward += self.rewards_scaling["tactical_attack_reward"]
                            break

            for coords, tile_desc in knowledge.visible_tiles.items():
                if (
                    tile_desc.character
                    and tile_desc.character.controller_name != self.name
                ):
                    reward += self.rewards_scaling["enemy_seen_reward"]
                    break

            if current_weapon != self.weapon_name:
                reward += self.rewards_scaling["weapon_pickup_reward"]
                self.weapon_name = current_weapon

            if current_health < self.last_health:
                reward += self.rewards_scaling["health_down_penalty"] * (
                    self.last_health - current_health
                )
            elif current_health > self.last_health:
                reward += self.rewards_scaling["health_up_reward"] * (
                    current_health - self.last_health
                )

            self.last_health = current_health

        return reward

    @property
    def name(self) -> str:
        return self.bot_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BLUE

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.trajectory = []
        self.last_obs = None
        self.last_action_idx = None
        self.last_policy = None
        self.last_value = None
        self.last_health = characters.CHAMPION_STARTING_HP
        self.weapon_name = "knife"
        if hasattr(self, "visited_tiles"):
            self.visited_tiles.clear()
        self.menhir_position = None
        self.last_menhir_dist = None
        self.last_game_score = 0.0
        self.last_tile = None
        self.wrapper.menhir_position = None
        self.terminal_indices = []

    def praise(self, score: int) -> None:
        if self.is_training and self.last_obs is not None:
            u_t = score * self.rewards_scaling["mid_rewards_multiplier"]
            self.trajectory.append(
                (
                    self.last_obs,
                    self.last_action_idx,
                    self.last_policy,
                    self.last_value,
                    u_t,
                )
            )

            if not hasattr(self, "terminal_indices"):
                self.terminal_indices = []
            self.terminal_indices.append(len(self.trajectory) - 1)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:

        obs = self.wrapper.encode(knowledge)

        if not self.is_training:
            knowledge_logger.log(level=logging.INFO, msg=str(knowledge))

            obs_out = ""
            for i, matrix in enumerate(obs):
                obs_out += f"\n--- {OBS_CHANNELS[i]} ---\n"
                obs_out += np.array2string(
                    matrix, precision=2, separator="|", edgeitems=8
                )
                obs_out += "\n"

            knowledge_logger.log(level=logging.INFO, msg=obs_out)

        reward = self.calculate_reward(knowledge)

        if self.last_obs is not None and self.is_training:
            self.trajectory.append(
                (
                    self.last_obs,
                    self.last_action_idx,
                    self.last_policy,
                    self.last_value,
                    reward,
                )
            )

        self.network.eval()
        policy, value = self.mcts.run(self.network, obs)

        if self.is_training:
            action_idx = np.random.choice(len(ACTIONS), p=policy)
        else:
            action_idx = np.argmax(policy)

        self.last_obs = obs
        self.last_action_idx = action_idx
        self.last_policy = policy
        self.last_value = value

        return ACTIONS[action_idx]
