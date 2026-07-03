"""
Priorytetowy bufor powtórek (Prioritized Experience Replay) z SumTree.

Przechowuje przejścia (s, a, r, s', done, maska) w prealokowanych
tablicach numpy/torch i umożliwia próbkowanie z prawdopodobieństwem
proporcjonalnym do priorytetu (|TD error| + ε) ^ alpha.

Różnice wobec poprzedniej naiwnej implementacji:
  1. SumTree — próbkowanie O(log n) zamiast O(n)
  2. Prealokowane tablice — brak narzutu GC z list krotek
  3. Korekcja IS (importance-sampling) z beta-annealing

Publiczne API:
  ReplayBuffer — jedyna klasa, używana przez PudzianBrain
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import torch


# ═══════════════════════════════════════════════════════════════════════════
#  SumTree — drzewo segmentowe do próbkowania O(log n)
# ═══════════════════════════════════════════════════════════════════════════

class _SumTree:
    """Drzewo segmentowe przechowujące sumy priorytetów.

    Pozwala na:
      • update(idx, priority) w O(log n)
      • sample() losowej próbki proporcjonalnej do priorytetów w O(log n)
      • odczyt sumy wszystkich priorytetów w O(1)
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        # Drzewo binarne — liście to priorytety, reszta to sumy
        self._tree = np.zeros(2 * capacity, dtype=np.float64)

    @property
    def total(self) -> float:
        """Suma wszystkich priorytetów (korzeń drzewa)."""
        return self._tree[1]

    def update(self, data_idx: int, priority: float) -> None:
        """Ustawia priorytet elementu o indeksie data_idx."""
        tree_idx = data_idx + self.capacity  # liść w drzewie
        delta = priority - self._tree[tree_idx]
        self._tree[tree_idx] = priority
        # Propaguj zmianę w górę do korzenia
        tree_idx >>= 1
        while tree_idx >= 1:
            self._tree[tree_idx] += delta
            tree_idx >>= 1

    def find(self, cumsum: float) -> int:
        """Znajduje indeks elementu odpowiadającego sumatywnej wartości.

        Schodzi od korzenia, wybierając lewe/prawe poddrzewo wg sumy.
        Zwraca data_idx (indeks w tablicy danych, nie w drzewie).
        """
        idx = 1  # korzeń
        while idx < self.capacity:
            left = 2 * idx
            if cumsum <= self._tree[left]:
                idx = left
            else:
                cumsum -= self._tree[left]
                idx = left + 1
        return idx - self.capacity  # konwersja tree_idx → data_idx

    def __getitem__(self, data_idx: int) -> float:
        """Zwraca priorytet elementu o indeksie data_idx."""
        return self._tree[data_idx + self.capacity]


# ═══════════════════════════════════════════════════════════════════════════
#  ReplayBuffer — główna klasa bufora
# ═══════════════════════════════════════════════════════════════════════════

# Stałe wymiarów — muszą być zgodne z brain.py (_STATE_DIM, _N_ACTIONS)
_STATE_DIM = 39
_N_ACTIONS = 14


class ReplayBuffer:
    """Priorytetowy bufor doświadczeń z SumTree.

    Parametry
    ---------
    capacity : int
        Maksymalna pojemność bufora.
    alpha : float
        Wykładnik priorytetyzacji.
        0.0 = próbkowanie jednorodne, 1.0 = pełna priorytetyzacja.
    """

    def __init__(self, capacity: int = 200_000, alpha: float = 0.6, device: str | torch.device = 'cpu',
                 priority_clip: float = 10.0) -> None:
        self.capacity = capacity
        self.alpha = alpha
        self.device = device
        # Górny limit surowego priorytetu (|TD|+ε). Bez niego pojedynczy
        # ogromny TD-error trwale zawyżał _max_priority → wszystkie NOWE
        # przejścia dostawały zawyżony priorytet i próbkowanie przechylało się
        # ku świeżości, dławiąc resztę bufora.
        self.priority_clip = priority_clip
        self._tree = _SumTree(capacity)

        # Prealokowane tablice danych (urządzenie konfigurowalne)
        self._states = torch.zeros(capacity, _STATE_DIM, dtype=torch.float32, device=self.device)
        self._next_states = torch.zeros(capacity, _STATE_DIM, dtype=torch.float32, device=self.device)
        self._next_masks = torch.zeros(capacity, _N_ACTIONS, dtype=torch.float32, device=self.device)
        self._actions = torch.zeros(capacity, dtype=torch.int64, device=self.device)
        self._rewards = torch.zeros(capacity, dtype=torch.float32, device=self.device)
        self._dones = torch.zeros(capacity, dtype=torch.float32, device=self.device)
        # Dyskonto efektywne γ^n dla zwrotów n-step (n może być < n_step na końcu
        # epizodu). Cel Bellmana: R^(n) + discount * Q_target(s', a*) * (1-done).
        self._discounts = torch.zeros(capacity, dtype=torch.float32, device=self.device)

        self._position: int = 0
        self._size: int = 0
        self._max_priority: float = 1.0  # cache max priorytetu

    # ── Dodawanie przejść ─────────────────────────────────────────────

    def push(
        self,
        state: torch.Tensor,
        action: int,
        reward: float,
        next_state: torch.Tensor,
        done: bool,
        next_mask: torch.Tensor,
        discount: float = 1.0,
    ) -> None:
        """Dodaje przejście do bufora.

        Nowe przejście otrzymuje najwyższy dotychczasowy priorytet
        (gwarantuje, że zostanie próbkowane przynajmniej raz).

        `reward` to zwrot n-step R^(n), a `discount` to γ^n (domyślnie 1.0 dla
        zgodności z wywołaniami 1-step). next_state/next_mask odnoszą się do
        stanu s_{t+n}.
        """
        idx = self._position

        # Zapisz dane w prealokowanych tablicach
        self._states[idx] = state.to(self.device)
        self._actions[idx] = action
        self._rewards[idx] = reward
        self._next_states[idx] = next_state.to(self.device)
        self._dones[idx] = float(done)
        self._next_masks[idx] = next_mask.to(self.device)
        self._discounts[idx] = discount

        # Nowe przejście dostaje max priorytet (podniesiony do alpha)
        self._tree.update(idx, self._max_priority ** self.alpha)

        # Przesuń wskaźnik
        self._position = (self._position + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    # ── Próbkowanie ───────────────────────────────────────────────────

    def sample(
        self, batch_size: int, beta: float,
    ) -> Tuple[
        torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor,
        torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, np.ndarray,
    ]:
        """Próbkuje mini-partię z uwzględnieniem priorytetów.

        Parametry
        ---------
        batch_size : int
            Rozmiar mini-partii.
        beta : float
            Wykładnik korekcji IS (importance-sampling).
            0.0 = brak korekcji, 1.0 = pełna korekcja.

        Zwraca
        ------
        (states, actions, rewards, next_states, dones,
         next_masks, discounts, weights, indices)
        """
        indices = np.empty(batch_size, dtype=np.int64)
        priorities = np.empty(batch_size, dtype=np.float64)

        # Stratyfikowane próbkowanie — dzielimy sumę priorytetów
        # na batch_size równych segmentów i losujemy z każdego.
        total = self._tree.total
        segment = total / batch_size

        for i in range(batch_size):
            low = segment * i
            high = segment * (i + 1)
            cumsum = np.random.uniform(low, high)
            data_idx = self._tree.find(cumsum)
            # Zabezpieczenie przed indeksem poza zakresem
            data_idx = min(data_idx, self._size - 1)
            indices[i] = data_idx
            priorities[i] = self._tree[data_idx]

        # Oblicz wagi korekcji IS
        probs = priorities / total
        weights = (self._size * probs) ** (-beta)
        weights = weights / weights.max()  # normalizacja do [0, 1]

        # Zbuduj tensory partii (zero-copy slice z prealokowanych tablic)
        states = self._states[indices]
        actions = self._actions[indices]
        rewards = self._rewards[indices]
        next_states = self._next_states[indices]
        dones = self._dones[indices]
        next_masks = self._next_masks[indices]
        discounts = self._discounts[indices]
        weights_t = torch.from_numpy(weights.astype(np.float32)).to(self.device)

        return states, actions, rewards, next_states, dones, next_masks, discounts, weights_t, indices

    # ── Aktualizacja priorytetów ──────────────────────────────────────

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray) -> None:
        """Aktualizuje priorytety na podstawie |TD error|.

        Parametry
        ---------
        indices : np.ndarray
            Indeksy próbkowanych przejść.
        td_errors : np.ndarray
            Wartości bezwzględne błędów TD.
        """
        for idx, td_err in zip(indices, td_errors):
            # Klip surowego priorytetu — ogranicza dominację outlierów.
            raw = min(abs(td_err) + 1e-6, self.priority_clip)
            priority = raw ** self.alpha
            self._tree.update(int(idx), priority)
            # Aktualizuj cache max priorytetu (surowy, bez alpha; już po klipie)
            if raw > self._max_priority:
                self._max_priority = raw

    # ── Rozmiar ───────────────────────────────────────────────────────

    def __len__(self) -> int:
        """Zwraca aktualną liczbę przejść w buforze."""
        return self._size
