"""
Moduł mózgu agenta Pudzian — Dueling Double DQN.

Zawiera:
    - DuelingDQN   — architektura sieci neuronowej Dueling DQN
    - PudzianBrain — główna klasa zarządzająca uczeniem i inferencją

Bufor doświadczeń (PER z SumTree) znajduje się w replay_buffer.py.
"""

from __future__ import annotations

import os
import queue as _queue
import stat
import random
from collections import deque
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from gupb.controller.pudzian.replay_buffer import ReplayBuffer

# ---------------------------------------------------------------------------
#  Stałe domyślne
# ---------------------------------------------------------------------------

_STATE_DIM: int = 39
_N_ACTIONS: int = 14


# ===========================================================================
#  1. Architektura sieci — Dueling DQN
# ===========================================================================


class DuelingDQN(nn.Module):
    """Architektura Dueling DQN z normalizacją warstw (LayerNorm).

    Sieć dzieli się na współdzielony ekstraktor cech oraz dwie głowice:
    wartości stanu V(s) i przewagi akcji A(s, a).

    Q(s, a) = V(s) + A(s, a) - mean_a(A(s, a))

    Parametry
    ---------
    state_dim : int
        Wymiarowość wektora stanu (domyślnie 39).
    n_actions : int
        Liczba dostępnych akcji (domyślnie 12).
    """

    def __init__(self, state_dim: int = _STATE_DIM, n_actions: int = _N_ACTIONS) -> None:
        super().__init__()
        self.state_dim = state_dim
        self.n_actions = n_actions

        # -- Współdzielone warstwy ekstrakcji cech --
        self.shared = nn.Sequential(
            nn.Linear(state_dim, 256),
            nn.ReLU(),
            nn.LayerNorm(256),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.LayerNorm(256),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.LayerNorm(128),
        )

        # -- Głowica wartości stanu V(s) --
        self.value_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

        # -- Głowica przewagi akcji A(s, a) --
        self.advantage_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, n_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Propagacja w przód — oblicza wartości Q dla wszystkich akcji.

        Parametry
        ---------
        x : torch.Tensor
            Tensor stanu o kształcie (batch, state_dim).

        Zwraca
        ------
        torch.Tensor
            Wartości Q o kształcie (batch, n_actions).
        """
        features = self.shared(x)
        value = self.value_head(features)           # (batch, 1)
        advantage = self.advantage_head(features)   # (batch, n_actions)

        # Agregacja Dueling: Q = V + (A - mean(A))
        q_values = value + advantage - advantage.mean(dim=1, keepdim=True)
        return q_values


# ===========================================================================
#  3. Główna klasa mózgu — PudzianBrain
# ===========================================================================


class PudzianBrain:
    """Mózg agenta Pudzian — Double DQN z siecią Dueling i buforem PER.

    Odpowiada za:
      • wybór akcji (ε-greedy z maskowaniem niedozwolonych ruchów),
      • przechowywanie doświadczeń w priorytetowym buforze,
      • trening sieci metodą Double DQN,
      • zapis i odczyt punktów kontrolnych (checkpoint).

    Parametry
    ---------
    model_path : str
        Ścieżka do pliku z zapisanym modelem (checkpoint).
    device : str, opcjonalnie
        Urządzenie obliczeniowe ('cuda' / 'cpu'). Jeśli None, wykrywane
        automatycznie.
    """

    def __init__(
    self,
    model_path: str,
    device: str | None = None,
    mode: str = "learner",
    transition_queue=None,
    replay_buffer_device: str | None = None,
    load_from_disk: bool = True,
    ):
        # -- Urządzenie --
        if device is not None:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.model_path = model_path
        self.mode = mode
        self.transition_queue = transition_queue

        # -- Sieć online (zawsze potrzebna — do inferencji i treningu) --
        self.online_net = DuelingDQN().to(self.device)

        # -- target_net + optimizer tylko w trybie learner (oszczędność RAM/VRAM
        #    w procesach aktorów, które robią wyłącznie inferencję)
        if self.mode == "learner":
            self.target_net = DuelingDQN().to(self.device)
            self.target_net.load_state_dict(self.online_net.state_dict())
            self.target_net.eval()  # Sieć docelowa nie jest trenowana bezpośrednio
            self.optimizer = optim.Adam(self.online_net.parameters(), lr=3e-4)
        else:
            self.target_net = None
            self.optimizer = None

        # -- Bufor doświadczeń (SumTree PER z replay_buffer.py) --
        # Bufor domyślnie na CPU — nawet przy treningu na CUDA. Przy 1.5M kapacitacji
        # to ~570 MB VRAM zaoszczędzone; batch=128 i tak kopiujemy do device w train_step.
        if self.mode == "learner":
            buf_device = torch.device(replay_buffer_device) if replay_buffer_device else torch.device("cpu")
            self.replay_buffer = ReplayBuffer(
                capacity=1_500_000,
                device=buf_device,
            )
        else:
            self.replay_buffer = None

        # -- Hiperparametry treningowe --
        # gamma 0.997 (zamiast 0.99): w battle-royale liczy się finalny placement,
        # a sygnał terminalny (±30) musi propagować się wstecz przez ~150 tur.
        # Przy 0.99 dyskonto 0.99^150≈0.22 czyniło bota krótkowzrocznym.
        self.gamma: float = 0.997
        self.tau: float = 0.005
        # batch 256: sieć jest mała, A100 i tak się nudzi (wąskie gardło = sym. gier),
        # większy batch = mniejsza wariancja gradientu i realne użycie GPU.
        self.batch_size: int = 256
        # train_start 10k (zamiast 5k): bufor 1.5M + stan 39D wymaga zróżnicowanej
        # próbki przed pierwszym gradientem (warmup epsilon=1.0 w train.py to zapewnia).
        self.train_start: int = 10000
        self.grad_clip: float = 1.0

        # -- Zwroty n-step (Ape-X) --
        # Akumulujemy okno n kolejnych przejść w epizodzie i emitujemy
        # przejście n-step z zwrotem R^(n)=Σ γ^k r_{t+k} oraz dyskontem γ^n.
        # Lepsze przypisanie zasługi w długich epizodach battle-royale niż 1-step.
        self.n_step: int = 3
        self._nstep_buffer: deque = deque()

        # -- Eksploracja (epsilon-greedy) --
        self.epsilon: float = 0.5
        self.epsilon_min: float = 0.03
        # Epsilon zanika przez ~800 gier (średnio 150 tur/grę = 120 000 kroków)
        self.epsilon_decay_steps: int = 120_000

        # -- Anihilacja beta (PER importance-sampling) --
        self.beta: float = 0.4
        self.beta_max: float = 1.0
        self.beta_anneal_steps: int = 800_000

        # -- Licznik kroków + ostatnia strata (do logowania) --
        self._step_count: int = 0
        self.last_loss: Optional[float] = None

        # -- Próba wczytania istniejącego checkpointu --
        if load_from_disk:
            self._load()

    # -----------------------------------------------------------------
    #  Wybór akcji
    # -----------------------------------------------------------------

    def choose_action(self, state: torch.Tensor, mask: torch.Tensor, greedy: bool = False) -> int:
        """Wybiera akcję metodą ε-greedy z maskowaniem niedozwolonych ruchów.

        Parametry
        ---------
        state : torch.Tensor
            Wektor stanu (1-D).
        mask : torch.Tensor
            Maska legalnych akcji — wartość niezerowa oznacza dozwoloną akcję.
        greedy : bool
            Jeśli True, pomija eksplorację (epsilon=0) — używane przy ewaluacji.

        Zwraca
        ------
        int
            Indeks wybranej akcji.
        """
        # Indeksy legalnych akcji.
        # NIE używamy torch.nonzero — jego wielowątkowy kernel CPU sporadycznie
        # rzuca "INTERNAL ASSERT FAILED ... TensorAdvancedIndexing.cpp" w procesach
        # aktorów (znany bug PyTorcha; set_num_threads(1) to tylko obejście,
        # które i tak czasem zawodzi). Maska jest mała (~liczba taktyk), więc
        # czysto-pythonowa iteracja po .tolist() jest równie szybka i niezawodna.
        legal_actions = [i for i, v in enumerate(mask.tolist()) if v]

        # Fallback: brak legalnych akcji (cała maska zerowa) — wybierz 0
        if not legal_actions:
            return 0

        # Eksploracja — losowa legalna akcja
        if not greedy and random.random() < self.epsilon:
            return random.choice(legal_actions)

        # Eksploatacja — najlepsza akcja wg sieci online
        with torch.no_grad():
            state_dev = state.unsqueeze(0).to(self.device)  # (1, state_dim)
            q_values = self.online_net(state_dev).squeeze(0)  # (n_actions,)

            # Maskowanie niedozwolonych akcji wartością -inf
            mask_dev = mask.to(self.device)
            q_values = q_values.masked_fill(mask_dev == 0, float("-inf"))

            return int(q_values.argmax().item())

    # -----------------------------------------------------------------
    #  Przechowywanie przejść
    # -----------------------------------------------------------------

    def store_transition(
    self,
    state,
    action,
    reward,
    next_state,
    done,
    next_mask,
    ):
        """Akumuluje przejście 1-step i emituje przejścia n-step.

        Utrzymujemy przesuwne okno do n_step kolejnych przejść epizodu. Gdy
        okno jest pełne, emitujemy przejście n-step dla najstarszego elementu
        i przesuwamy okno. Na końcu epizodu (done=True) wypłukujemy wszystkie
        pozostałe pozycje z częściowym horyzontem (n < n_step).

        Emisja zależy od trybu: actor → kolejka, learner → bezpośrednio bufor.
        """
        self._nstep_buffer.append(
            (state, int(action), float(reward), next_state, float(done), next_mask)
        )

        # Okno jeszcze niepełne i epizod trwa → czekamy na kolejne kroki.
        if len(self._nstep_buffer) < self.n_step and not done:
            return

        if done:
            # Terminal: wypłucz każdą pozycję startową aż do stanu końcowego.
            while self._nstep_buffer:
                self._emit_transition(self._build_nstep())
                self._nstep_buffer.popleft()
        else:
            # Pełne okno: emituj najstarszy, przesuń.
            self._emit_transition(self._build_nstep())
            self._nstep_buffer.popleft()

    def _build_nstep(self) -> tuple:
        """Buduje przejście n-step zaczynające się od czoła okna.

        Zwraca (state, action, R^(n), next_state, done, next_mask, γ^n), gdzie
        sumowanie zatrzymuje się na pierwszym przejściu terminalnym w oknie.
        """
        state, action = self._nstep_buffer[0][0], self._nstep_buffer[0][1]
        cum_reward = 0.0
        discount = 1.0
        next_state = self._nstep_buffer[0][3]
        next_mask = self._nstep_buffer[0][5]
        done = 0.0
        for (_, _, r, ns, d, nm) in self._nstep_buffer:
            cum_reward += discount * r
            discount *= self.gamma          # po pętli = γ^(liczba kroków)
            next_state, next_mask, done = ns, nm, d
            if d:                            # terminal kończy zwrot n-step
                break
        return state, action, cum_reward, next_state, done, next_mask, discount

    def _emit_transition(self, transition: tuple) -> None:
        """Wysyła gotowe przejście n-step do kolejki (actor) lub bufora (learner)."""
        state, action, reward, next_state, done, next_mask, discount = transition

        if self.mode == "actor":
            if self.transition_queue is None:
                return
            item = (
                state.cpu(), action, reward,
                next_state.cpu(), done, next_mask.cpu(), discount,
            )
            try:
                # Timeout zamiast blocking put — jeśli learner się zatka,
                # aktor drop'uje transition zamiast zawisnąć.
                self.transition_queue.put(item, timeout=1.0)
            except _queue.Full:
                pass  # learner nie nadąża — drop'ujemy transition
            except Exception:
                pass  # zabezpieczenie przy shutdown (broken pipe itd.)
        else:
            if self.replay_buffer is not None:
                self.replay_buffer.push(
                    state, action, reward, next_state, done, next_mask, discount,
                )

    def reset_nstep_buffer(self) -> None:
        """Czyści okno n-step na granicy epizodu.

        Wołane z Pudzian.reset(). Zwykle okno jest już puste (terminal z
        praise() wypłukuje je), ale gdy epizod skończy się bez terminalnego
        store_transition (np. last_state==None), gwarantuje brak mostkowania
        przejść między dwoma epizodami.
        """
        self._nstep_buffer.clear()

    # -----------------------------------------------------------------
    #  Krok treningowy
    # -----------------------------------------------------------------

    def train_step(self) -> Optional[float]:
        """Wykonuje jeden krok treningowy Double DQN z priorytetowym buforem.

        Zwraca
        ------
        Optional[float]
            Wartość funkcji straty lub None, jeśli bufor nie zawiera
            wystarczającej liczby próbek.
        """
        if self.mode != "learner":
            return None
        if len(self.replay_buffer) < self.train_start:
            return None

        # -- Próbkowanie mini-partii --
        (
            states,
            actions,
            rewards,
            next_states,
            dones,
            next_masks,
            discounts,
            weights,
            indices,
        ) = self.replay_buffer.sample(self.batch_size, self.beta)

        # Przeniesienie tensorów na urządzenie obliczeniowe
        states = states.to(self.device)
        actions = actions.to(self.device)
        rewards = rewards.to(self.device)
        next_states = next_states.to(self.device)
        dones = dones.to(self.device)
        next_masks = next_masks.to(self.device)
        discounts = discounts.to(self.device)
        weights = weights.to(self.device)

        # -- Obliczanie obecnych wartości Q --
        q_values = self.online_net(states)  # (batch, n_actions)
        q_current = q_values.gather(1, actions.unsqueeze(1)).squeeze(1)  # (batch,)

        # -- Obliczanie celów Double DQN --
        with torch.no_grad():
            # Sieć online wybiera najlepszą akcję w następnym stanie
            next_q_online = self.online_net(next_states)  # (batch, n_actions)
            # Maskowanie niedozwolonych akcji
            next_q_online = next_q_online.masked_fill(next_masks == 0, float("-inf"))
            next_actions = next_q_online.argmax(dim=1)  # (batch,)

            # Sieć docelowa ocenia wartość wybranej akcji
            next_q_target = self.target_net(next_states)  # (batch, n_actions)
            next_q = next_q_target.gather(1, next_actions.unsqueeze(1)).squeeze(1)

            # Cel Bellmana n-step: R^(n) + γ^n * Q_target(s', a*) * (1 - done)
            # γ^n (discounts) jest per-przejście, bo n bywa < n_step na końcu epizodu.
            targets = rewards + discounts * next_q * (1.0 - dones)

        # -- Obliczanie ważonej straty Huber (stabilniejsza niż MSE z PER) --
        td_errors = q_current - targets
        huber = nn.functional.smooth_l1_loss(q_current, targets, reduction='none')
        loss = (weights * huber).mean()

        # -- Propagacja wsteczna --
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online_net.parameters(), self.grad_clip)
        self.optimizer.step()

        # -- Aktualizacja priorytetów w buforze --
        td_errors_np = td_errors.detach().cpu().numpy()
        self.replay_buffer.update_priorities(indices, np.abs(td_errors_np))

        # -- Miękka aktualizacja sieci docelowej --
        self._soft_update()

        # -- Zanik epsilona i wzrost beta --
        self._step_count += 1
        self._decay_epsilon()
        self._anneal_beta()

        loss_value = loss.item()
        self.last_loss = loss_value
        return loss_value

    # -----------------------------------------------------------------
    #  Zapis i odczyt modelu
    # -----------------------------------------------------------------

    def save(self) -> None:
        """Zapisuje punkt kontrolny (checkpoint) modelu na dysk."""
        if self.mode != "learner":
            return  # aktorzy nie mają target_net/optimizer
        checkpoint = {
            "online_net": self.online_net.state_dict(),
            "target_net": self.target_net.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "epsilon": self.epsilon,
            "step_count": self._step_count,
            "beta": self.beta,
        }
        # Tworzenie katalogów, jeśli nie istnieją
        dirpath = os.path.dirname(self.model_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        # Upewnij się, że istniejący plik nie jest tylko do odczytu
        if os.path.exists(self.model_path):
            os.chmod(self.model_path, os.stat(self.model_path).st_mode | stat.S_IWRITE)
        tmp_path = f"{self.model_path}.tmp"
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        torch.save(checkpoint, tmp_path)
        os.replace(tmp_path, self.model_path)

    def _load(self) -> None:
        """Wczytuje punkt kontrolny (checkpoint), jeśli plik istnieje."""
        if not os.path.isfile(self.model_path):
            return

        checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=False)

        # Niezgodność rozmiaru (np. zmiana przestrzeni akcji 12→14 taktyk) →
        # stary checkpoint jest niekompatybilny. Zamiast krashować przy
        # imporcie/starcie, pomijamy ładowanie i ruszamy od świeżej sieci.
        try:
            self.online_net.load_state_dict(checkpoint["online_net"])
            if self.target_net is not None:
                self.target_net.load_state_dict(checkpoint["target_net"])
            if self.optimizer is not None:
                self.optimizer.load_state_dict(checkpoint["optimizer"])
        except (RuntimeError, ValueError, KeyError) as exc:
            print(f"[BRAIN] Pomijam niezgodny checkpoint ({self.model_path}): {exc}. "
                  f"Startuję od świeżej sieci.")
            return

        self.epsilon = checkpoint.get("epsilon", self.epsilon)
        self._step_count = checkpoint.get("step_count", self._step_count)
        self.beta = checkpoint.get("beta", self.beta)

    # -----------------------------------------------------------------
    #  Pomocnicze metody prywatne
    # -----------------------------------------------------------------

    def _soft_update(self) -> None:
        """Miękka aktualizacja sieci docelowej (uśrednianie Polyaka).

        θ_target ← τ · θ_online + (1 − τ) · θ_target
        """
        for target_param, online_param in zip(
            self.target_net.parameters(), self.online_net.parameters()
        ):
            target_param.data.copy_(
                self.tau * online_param.data + (1.0 - self.tau) * target_param.data
            )

    def _decay_epsilon(self) -> None:
        """Liniowy zanik epsilona.
        
        Zmieniono na zanik względem obecnej wartości, aby ręczne 
        podbicia eksploracji (z train.py przy stagnacji) nie były 
        natychmiast nadpisywane przez funkcję zależną od _step_count.
        """
        decay_rate = (0.5 - self.epsilon_min) / self.epsilon_decay_steps
        if self.epsilon > self.epsilon_min:
            self.epsilon = max(self.epsilon_min, self.epsilon - decay_rate)

    def _anneal_beta(self) -> None:
        """Liniowy wzrost beta (PER) od wartości początkowej do maksymalnej.

        Wzrost odbywa się w ciągu *beta_anneal_steps* kroków.
        """
        fraction = min(1.0, self._step_count / self.beta_anneal_steps)
        self.beta = 0.4 + fraction * (self.beta_max - 0.4)

    # -----------------------------------------------------------------
    #  Kompatybilność wsteczna
    # -----------------------------------------------------------------

    def decay_epsilon(self) -> None:
        """Metoda pusta — zachowana dla kompatybilności z train.py (reset())."""
        pass
