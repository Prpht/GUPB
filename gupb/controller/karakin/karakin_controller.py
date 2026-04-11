from __future__ import annotations
import os
import pickle
import collections

import numpy as np
import sklearn.preprocessing as skl_preprocessing

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

ALMOST_INFINITE_STEP = 100000

class KarakinController(controller.Controller):
    def __init__(
            self,
            first_name: str = "Karakin_SARSA",
            step_size: float = 0.1,
            step_no: int = 3,
            experiment_rate: float = 1.0,
            discount_factor: float = 0.9,
            is_training: bool = True
        ) -> None:
        self.first_name: str = first_name
        self._center: coordinates.Coords | None = None
        self.file_path = f"{self.first_name}_qtable.pkl"
        
        self.step_size: float = step_size if is_training else 0.0
        self.step_no: int = step_no
        self.experiment_rate: float = experiment_rate if is_training else 0.0
        self.experiment_rate_min: float = 0.05
        self.experiment_rate_decay: float = 0.995
        self.discount_factor: float = discount_factor
        self.is_training: bool = is_training
        self.available_actions = ["STEP_FORWARD", "TURN_LEFT", "TURN_RIGHT", "ATTACK"]
        
        self.q: dict[tuple[tuple, str], float] = collections.defaultdict(float)
        self._load_q_table()
        
        self.current_step: int = 0
        self.final_step: int = ALMOST_INFINITE_STEP
        self.states: dict[int, tuple] = dict()
        self.actions: dict[int, str] = dict()
        self.rewards: dict[int, float] = dict()
        
        self.last_health = characters.CHAMPION_STARTING_HP

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KarakinController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def behavior_policy(self, state: tuple, actions: list[str]) -> dict[str, float]:
        return self.epsilon_greedy_policy(state, actions)

    def epsilon_greedy_policy(self, state: tuple, actions: list[str]) -> dict[str, float]:
        greedy_probs = self._greedy_probabilities(state, actions)
        random_probs = self._random_probabilities(actions)

        probabilities = (1 - self.experiment_rate) * greedy_probs + self.experiment_rate * random_probs
        return {action: probability for action, probability in zip(actions, probabilities)}

    def _greedy_probabilities(self, state: tuple, actions: list[str]) -> np.ndarray:
        values = [self.q[state, action] for action in actions]
        maximal_spots = (np.array(values) == np.max(values)).astype(float)
        return self._normalise(maximal_spots)

    @staticmethod
    def _random_probabilities(actions: list[str]) -> np.ndarray:
        maximal_spots = np.array([1.0 for _ in actions])
        return KarakinController._normalise(maximal_spots)

    @staticmethod
    def _normalise(probabilities: np.ndarray) -> np.ndarray:
        return skl_preprocessing.normalize(probabilities.reshape(1, -1), norm='l1')[0]

    @staticmethod
    def _select_action(actions_distribution: dict[str, float]) -> str:
        actions = list(actions_distribution.keys())
        probabilities = list(actions_distribution.values())
        i = np.random.choice(list(range(len(actions))), p=probabilities)
        return actions[i]

    def eval(self) -> KarakinController:
        self.is_training = False
        self.experiment_rate = 0.0
        self.step_size = 0.0
        return self

    def _access_index(self, index: int) -> int:
        return index % (self.step_no + 1)

    def _return_value(self, update_step: int) -> float:
        return_value = 0.0
        end_step = min(update_step + self.step_no, self.final_step)

        for i in range(update_step + 1, end_step + 1):
            reward = self.rewards[self._access_index(i)]
            return_value += reward * (self.discount_factor ** (i - update_step - 1))

        if update_step + self.step_no < self.final_step:
            state_last = self.states[self._access_index(update_step + self.step_no)]
            action_last = self.actions[self._access_index(update_step + self.step_no)]
            return_value += self.q[state_last, action_last] * (self.discount_factor ** self.step_no)

        return return_value

    def _perform_update(self, update_step: int) -> None:
        if not self.is_training or update_step < 0:
            return
            
        return_value = self._return_value(update_step)
        state_t = self.states[self._access_index(update_step)]
        action_t = self.actions[self._access_index(update_step)]
        
        self.q[state_t, action_t] += self.step_size * (return_value - self.q[state_t, action_t])

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            state = self._extract_state(knowledge)

            if self.current_step > 0:
                reward = self._calculate_reward(knowledge)
                self.rewards[self._access_index(self.current_step)] = reward

            self.states[self._access_index(self.current_step)] = state

            action_dist = self.behavior_policy(state, self.available_actions)
            action = self._select_action(action_dist)
            self.actions[self._access_index(self.current_step)] = action

            update_step = self.current_step - self.step_no
            if update_step >= 0:
                self._perform_update(update_step)

            self.current_step += 1
            
            action_map = {
                "STEP_FORWARD": characters.Action.STEP_FORWARD,
                "TURN_LEFT": characters.Action.TURN_LEFT,
                "TURN_RIGHT": characters.Action.TURN_RIGHT,
                "ATTACK": characters.Action.ATTACK
            }
            return action_map[action]

        except Exception as e:
            print(f"Error in decide: {e}")
            return characters.Action.TURN_LEFT

    def praise(self, score: int) -> None:
        self.final_step = self.current_step
        
        terminal_reward = float(score * 10)
        self.rewards[self._access_index(self.final_step)] = terminal_reward
        
        if self.is_training:
            for update_step in range(self.final_step - self.step_no, self.final_step):
                self._perform_update(update_step)
                
            self._save_q_table()
            
            if self.experiment_rate > self.experiment_rate_min:
                self.experiment_rate *= self.experiment_rate_decay

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.current_step = 0
        self.final_step = ALMOST_INFINITE_STEP
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        
        self.last_health = characters.CHAMPION_STARTING_HP
        self._center = coordinates.Coords(12, 12)

    def _extract_state(self, knowledge: characters.ChampionKnowledge) -> tuple:
        pos = knowledge.position
        visible = knowledge.visible_tiles
        own_tile = visible.get(pos)
        
        if not own_tile or not own_tile.character:
            return ("None", "11+", False, False)
            
        facing = own_tile.character.facing
        dist = "11+"
        if self._center:
            d = abs(pos.x - self._center.x) + abs(pos.y - self._center.y)
            if d <= 5: dist = "0-5"
            elif d <= 10: dist = "6-10"

        enemy_in_range = False
        path_blocked = False
        tile_in_front_pos = coordinates.add_coords(pos, facing.value)
        tile_in_front = visible.get(tile_in_front_pos)
        
        if tile_in_front:
            if tile_in_front.type in ("wall", "sea"):
                path_blocked = True
            if tile_in_front.character:
                path_blocked = True
                enemy_in_range = True

        mist_dir = "None"
        for d_name, d_vec in [("Front", facing.value), ("Back", facing.opposite().value), 
                              ("Left", facing.turn_left().value), ("Right", facing.turn_right().value)]:
            check_pos = coordinates.add_coords(pos, d_vec)
            if check_pos in visible and any(e.type == "mist" for e in visible[check_pos].effects):
                mist_dir = d_name
                break

        return (mist_dir, dist, enemy_in_range, path_blocked)

    def _calculate_reward(self, knowledge: characters.ChampionKnowledge) -> float:
        reward = -0.1
        pos = knowledge.position
        own_tile = knowledge.visible_tiles.get(pos)
        if not own_tile or not own_tile.character:
            return reward

        current_health = own_tile.character.health
        if current_health < self.last_health:
            reward -= 10.0
        self.last_health = current_health
        
        return reward

    def _save_q_table(self):
        try:
            with open(self.file_path, "wb") as f:
                pickle.dump(dict(self.q), f)
        except Exception as e:
            print(f"Failed to save Q-table: {e}")

    def _load_q_table(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "rb") as f:
                    loaded_dict = pickle.load(f)
                    self.q.update(loaded_dict)
            except Exception as e:
                print(f"Corrupted Q-table detected: {e}. Deleting and starting fresh.")
                os.remove(self.file_path)

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KARAKIN