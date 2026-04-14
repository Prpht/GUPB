import os
import torch
import numpy as np
from typing import Optional

from gupb import controller
from gupb.model import arenas, characters

from .network import ActorCritic, NUM_ACTIONS
from .encoder import StateEncoder
from .memory import BotMemory
from .heuristics import HeuristicLayer

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), 'weights_checkpoint980.pt')
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


class Pudzian(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name = first_name
        self.network = ActorCritic().to(DEVICE)
        self.encoder = StateEncoder()
        self.memory = BotMemory()
        self.heuristics = HeuristicLayer()
        self._training_mode = True

        if os.path.exists(WEIGHTS_PATH):
            self.network.load_state_dict(
                torch.load(WEIGHTS_PATH, map_location=DEVICE)
            )
            self.network.eval()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.memory.update(knowledge)

            # Heurystyki PRZED siecią
            override = self.heuristics.get_action(knowledge, self.memory)
            if override is not None:
                override = self._sanitize_action_against_amulet(override, knowledge)
                if self._training_mode:
                    # Zapisz akcję heurystyki do bufora żeby sieć się uczyła
                    state_vec = self.encoder.encode(knowledge, self.memory)
                    action_idx = self._action_to_idx(override)
                    reward = self.memory.compute_step_reward(knowledge, action_idx)

                    state_tensor = torch.FloatTensor(state_vec).unsqueeze(0).to(DEVICE)
                    _, log_prob, value = self.network.act(state_tensor, greedy=False)

                    self.memory.states.append(state_vec)
                    self.memory.actions.append(action_idx)
                    self.memory.log_probs.append(log_prob)
                    self.memory.values.append(value)
                    self.memory.rewards.append(reward)
                    self.memory.dones.append(False)
                    self.memory.last_action = action_idx

                return override

            # Sieć decyduje
            state_vec = self.encoder.encode(knowledge, self.memory)
            state_tensor = torch.FloatTensor(state_vec).unsqueeze(0).to(DEVICE)

            if self._training_mode:
                action_idx, log_prob, value = self.network.act(state_tensor, greedy=False)
            else:
                action_idx, log_prob, value = self.network.act(state_tensor, greedy=True)

            proposed_action = self._idx_to_action(action_idx)
            safe_action = self._sanitize_action_against_amulet(proposed_action, knowledge)
            action_idx = self._action_to_idx(safe_action)

            if self._training_mode:
                reward = self.memory.compute_step_reward(knowledge, action_idx)
                self.memory.states.append(state_vec)
                self.memory.actions.append(action_idx)
                self.memory.log_probs.append(log_prob)
                self.memory.values.append(value)
                self.memory.rewards.append(reward)
                self.memory.dones.append(False)

            self.memory.last_action = action_idx
            return self._idx_to_action(action_idx)

        except Exception as e:
    
            import traceback
            traceback.print_exc()
            return characters.Action.STEP_FORWARD

    def praise(self, score: int) -> None:
        if not self._training_mode:
            return
        if not self.memory.rewards:
            return

        # Nagroda za miejsce
        final_reward = score * 1.0

        # Bonus za agresję
        attack_bonus = self.memory.attacks_landed * 3.0
        final_reward += attack_bonus

        self.memory.rewards[-1] += final_reward
        self.memory.dones[-1] = True

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.memory.reset(arena_description)

    @property
    def name(self) -> str:
        return f'Pudzian_{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED

    def _idx_to_action(self, idx: int) -> characters.Action:
        actions = [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
            characters.Action.STEP_BACKWARD,
            characters.Action.STEP_LEFT,
            characters.Action.STEP_RIGHT,
            characters.Action.ATTACK,
            characters.Action.DO_NOTHING,
        ]
        return actions[idx]

    def _action_to_idx(self, action: characters.Action) -> int:
        actions = [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
            characters.Action.STEP_BACKWARD,
            characters.Action.STEP_LEFT,
            characters.Action.STEP_RIGHT,
            characters.Action.ATTACK,
            characters.Action.DO_NOTHING,
        ]
        return actions.index(action)

    def _sanitize_action_against_amulet(
            self,
            action: characters.Action,
            knowledge: characters.ChampionKnowledge,
    ) -> characters.Action:
        if not self._would_step_on_amulet(action, knowledge):
            return action

        # Nie wchodź na pole z amuletem: wybierz bezpieczną akcję niemobilną.
        if action == characters.Action.STEP_FORWARD:
            return characters.Action.TURN_RIGHT
        return characters.Action.TURN_LEFT

    def _would_step_on_amulet(
            self,
            action: characters.Action,
            knowledge: characters.ChampionKnowledge,
    ) -> bool:
        if action not in {
            characters.Action.STEP_FORWARD,
            characters.Action.STEP_BACKWARD,
            characters.Action.STEP_LEFT,
            characters.Action.STEP_RIGHT,
        }:
            return False

        facing = self.memory.last_facing
        if action == characters.Action.STEP_FORWARD:
            step_facing = facing
        elif action == characters.Action.STEP_BACKWARD:
            step_facing = facing.opposite()
        elif action == characters.Action.STEP_LEFT:
            step_facing = facing.turn_left()
        else:
            step_facing = facing.turn_right()

        pos = knowledge.position
        target_pos = (
            pos[0] + step_facing.value[0],
            pos[1] + step_facing.value[1],
        )
        tile = knowledge.visible_tiles.get(target_pos)
        return bool(tile and tile.loot is not None and tile.loot.name == 'amulet')