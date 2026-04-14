"""
Skrypt treningowy - odpal lokalnie żeby wytrenować bota.
Wyniki zapisuje do weights.pt w tym samym folderze.

Użycie:
    python -m gupb.controller.pudzian.train
"""
import logging
import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Categorical
import torch.nn.functional as F
from typing import List

logging.getLogger('verbose').setLevel(logging.CRITICAL)
logging.disable(logging.WARNING)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from gupb.controller.pudzian.pudzian import Pudzian, WEIGHTS_PATH, DEVICE
from gupb.controller.pudzian.network import ActorCritic, NUM_ACTIONS
from gupb.controller import random as random_ctrl
from gupb.model import games, arenas

# ============================================================
LEARNING_RATE = 3e-4
GAMMA = 0.99
GAE_LAMBDA = 0.95
PPO_CLIP = 0.2
PPO_EPOCHS = 8
ENTROPY_COEF = 0.03
VALUE_COEF = 0.1
MAX_GRAD_NORM = 0.5

GAMES_PER_UPDATE = 32
TOTAL_UPDATES = 1000
SELF_PLAY_START = 100
SAVE_EVERY = 20

ARENA_NAMES = ['ordinary_chaos']
NUM_RANDOM_OPPONENTS = 10
# ============================================================


def compute_gae(
        rewards: List[float],
        values: List[float],
        dones: List[bool],
        last_value: float,
        gamma: float = GAMMA,
        lam: float = GAE_LAMBDA,
) -> tuple:
    advantages = []
    returns = []
    gae = 0.0
    next_value = last_value

    for reward, value, done in zip(
            reversed(rewards),
            reversed(values),
            reversed(dones)
    ):
        if done:
            next_value = 0.0
            gae = 0.0

        delta = reward + gamma * next_value - value
        gae = delta + gamma * lam * gae
        advantages.insert(0, gae)
        returns.insert(0, gae + value)
        next_value = value

    return advantages, returns


def ppo_update(
        network: ActorCritic,
        optimizer: optim.Optimizer,
        all_states: List[np.ndarray],
        all_actions: List[int],
        all_log_probs: List[float],
        all_advantages: List[float],
        all_returns: List[float],
) -> dict:
    states_t = torch.FloatTensor(np.array(all_states)).to(DEVICE)
    actions_t = torch.LongTensor(all_actions).to(DEVICE)
    old_log_probs_t = torch.FloatTensor(all_log_probs).to(DEVICE)
    advantages_t = torch.FloatTensor(all_advantages).to(DEVICE)
    returns_t = torch.FloatTensor(all_returns).to(DEVICE)

    advantages_t = (advantages_t - advantages_t.mean()) / (advantages_t.std() + 1e-8)

    total_policy_loss = 0
    total_value_loss = 0
    total_entropy = 0

    for _ in range(PPO_EPOCHS):
        log_probs, values, entropy = network.evaluate(states_t, actions_t)

        ratio = torch.exp(log_probs - old_log_probs_t)

        surr1 = ratio * advantages_t
        surr2 = torch.clamp(ratio, 1 - PPO_CLIP, 1 + PPO_CLIP) * advantages_t
        policy_loss = -torch.min(surr1, surr2).mean()

        value_loss = F.mse_loss(values, returns_t)

        loss = policy_loss + VALUE_COEF * value_loss - ENTROPY_COEF * entropy.mean()

        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(network.parameters(), MAX_GRAD_NORM)
        optimizer.step()

        total_policy_loss += policy_loss.item()
        total_value_loss += value_loss.item()
        total_entropy += entropy.mean().item()

    return {
        'policy_loss': total_policy_loss / PPO_EPOCHS,
        'value_loss': total_value_loss / PPO_EPOCHS,
        'entropy': total_entropy / PPO_EPOCHS,
    }


def run_training_games(
        our_bot: Pudzian,
        opponents: list,
        arena_name: str,
        n_games: int,
) -> tuple:
    """Odpala n_games gier i zbiera doświadczenia"""
    total_steps = 0
    our_scores = []      # <- zbieramy score z każdej gry
    total_attacks = 0    # <- zbieramy ataki z każdej gry

    # Wyczyść bufor
    our_bot.memory.states = []
    our_bot.memory.actions = []
    our_bot.memory.log_probs = []
    our_bot.memory.values = []
    our_bot.memory.rewards = []
    our_bot.memory.dones = []

    for game_idx in range(n_games):
        import random
        all_controllers = [our_bot] + opponents
        random.shuffle(all_controllers)

        try:
            game = games.Game(
                game_no=game_idx,
                arena_name=arena_name,
                to_spawn=all_controllers,
            )

            while not game.finished:
                game.cycle()

            # Zbierz score i ataki przed praise
            scores = game.score()
            our_score = scores.get(our_bot, 1)
            our_scores.append(our_score)
            total_attacks += our_bot.memory.attacks_landed

            for ctrl, score in scores.items():
                try:
                    ctrl.praise(score)
                except Exception:
                    pass

            total_steps += our_bot.memory.turn_no

        except Exception as e:
            print(f"  Błąd w grze {game_idx}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Statystyki serii gier
    avg_survival = our_bot.memory.turn_no / max(n_games, 1)
    avg_score = np.mean(our_scores) if our_scores else 0
    avg_attacks = total_attacks / max(n_games, 1)
    wins = sum(1 for s in our_scores if s == max(our_scores))

    print(
        f"  Survival: {avg_survival:.1f} tur | "
        f"Avg score: {avg_score:.2f} | "
        f"Avg attacks: {avg_attacks:.1f} | "
        f"Wins: {wins}/{n_games}"
    )

    return total_steps, avg_score, avg_attacks


def collect_experience(our_bot: Pudzian) -> tuple:
    if not our_bot.memory.states:
        return [], [], [], [], []

    # GAE na oryginalnych nagrodach
    advantages, returns = compute_gae(
        our_bot.memory.rewards,
        our_bot.memory.values,
        our_bot.memory.dones,
        last_value=0.0,
    )

    # Normalizuj advantages (nie rewards)
    advantages = np.array(advantages)
    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

    return (
        our_bot.memory.states,
        our_bot.memory.actions,
        our_bot.memory.log_probs,
        advantages.tolist(),
        returns,
    )


def main():
    print(f"Trening na urządzeniu: {DEVICE}")
    print(f"Łączna liczba aktualizacji: {TOTAL_UPDATES}")
    print(f"Gier na aktualizację: {GAMES_PER_UPDATE}")
    print("=" * 50)

    our_bot = Pudzian("Pudzian")
    our_bot._training_mode = True

    if os.path.exists(WEIGHTS_PATH):
        print("Znaleziono istniejące wagi - kontynuuję trening")
        our_bot.network.load_state_dict(
            torch.load(WEIGHTS_PATH, map_location=DEVICE)
        )

    our_bot.network.train()
    optimizer = optim.Adam(our_bot.network.parameters(), lr=LEARNING_RATE)

    frozen_bot = Pudzian("FrozenPudzian")
    frozen_bot._training_mode = False

    random_opponents = [
        random_ctrl.RandomController(f"Random{i}")
        for i in range(NUM_RANDOM_OPPONENTS)
    ]

    best_avg_score = -float('inf')
    score_history = []
    avg_score_history = []    # <- historia score z gier

    for update in range(TOTAL_UPDATES):
        # Wyczyść bufor
        our_bot.memory.states = []
        our_bot.memory.actions = []
        our_bot.memory.log_probs = []
        our_bot.memory.values = []
        our_bot.memory.rewards = []
        our_bot.memory.dones = []

        # Dobierz przeciwników
        if update >= SELF_PLAY_START:
            frozen_bot.network.load_state_dict(
                our_bot.network.state_dict()
            )
            opponents = random_opponents[:2] + [frozen_bot]
        else:
            opponents = random_opponents

        arena_name = ARENA_NAMES[update % len(ARENA_NAMES)]

        # Zbierz doświadczenia
        steps, avg_score, avg_attacks = run_training_games(
            our_bot=our_bot,
            opponents=opponents,
            arena_name=arena_name,
            n_games=GAMES_PER_UPDATE,
        )

        avg_score_history.append(avg_score)
        recent_avg_score = np.mean(avg_score_history[-20:])

        # Pobierz dane
        (all_states, all_actions, all_log_probs,
         all_advantages, all_returns) = collect_experience(our_bot)

        if len(all_states) < 10:
            print(f"Update {update}: za mało danych, pomijam")
            continue

        # PPO update
        losses = ppo_update(
            network=our_bot.network,
            optimizer=optimizer,
            all_states=all_states,
            all_actions=all_actions,
            all_log_probs=all_log_probs,
            all_advantages=all_advantages,
            all_returns=all_returns,
        )
        if update % 10 == 0:
            params = list(our_bot.network.parameters())
            param_sum = sum(p.sum().item() for p in params)
            test_state = torch.zeros(1, 35).to(DEVICE)
            with torch.no_grad():
                logits, _ = our_bot.network(test_state)
                probs = torch.softmax(logits, dim=-1)
            print(f"  Param sum: {param_sum:.4f} | Action probs: {probs.cpu().numpy().round(3)}")

        avg_reward = np.mean(our_bot.memory.rewards) if our_bot.memory.rewards else 0
        score_history.append(avg_reward)
        recent_avg = np.mean(score_history[-20:])

        if update % 10 == 0:
            print(
                f"Update {update:4d} | "
                f"Steps: {steps:5d} | "
                f"Avg reward: {avg_reward:6.3f} | "
                f"Recent avg: {recent_avg:6.3f} | "
                f"Avg score: {recent_avg_score:.2f} | "
                f"Attacks/game: {avg_attacks:.1f} | "
                f"Value loss: {losses['value_loss']:6.2f} | "
                f"Entropy: {losses['entropy']:5.3f}"
            )

        # Zapisz najlepsze wagi na podstawie score z gier
        if recent_avg_score > best_avg_score and update > 20:
            best_avg_score = recent_avg_score
            torch.save(our_bot.network.state_dict(), WEIGHTS_PATH)
            print(f"  -> Zapisano wagi (avg score: {recent_avg_score:.2f})")

        if update % SAVE_EVERY == 0 and update > 0:
            checkpoint_path = WEIGHTS_PATH.replace('.pt', f'_checkpoint_{update}.pt')
            torch.save(our_bot.network.state_dict(), checkpoint_path)

    torch.save(our_bot.network.state_dict(), WEIGHTS_PATH)
    print("=" * 50)
    print(f"Trening zakończony. Wagi zapisane do: {WEIGHTS_PATH}")


if __name__ == '__main__':
    main()