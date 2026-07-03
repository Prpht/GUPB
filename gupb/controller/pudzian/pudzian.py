"""
Kontroler Pudzian — Dueling Double DQN z 12 mikro-taktykami.

Architektura hierarchiczna:
  Sieć DQN wybiera mikro-taktykę (cel strategiczny),
  heurystyki tłumaczą ją na konkretną akcję w grze (ruch/atak/obrót).
"""

import os
from typing import Dict, Optional, List, Tuple

import torch

from gupb import controller
from gupb.model import arenas, characters, coordinates
from gupb.controller.pudzian.brain import PudzianBrain
from gupb.controller.pudzian.heuristics import PudzianHeuristics, _WEAPON_TIERS
from gupb.controller.pudzian.reward import RewardContext, compute_reward
from gupb.controller.pudzian.tactics import Tactic, N_TACTICS


# ═══════════════════════════════════════════════════════════════════════════
#  Mikro-taktyki (przestrzeń akcji DQN) — definicje w tactics.py
# ═══════════════════════════════════════════════════════════════════════════
# Tactic + N_TACTICS importowane z tactics.py (osobny moduł, żeby reward.py
# mógł je używać bez circular import).

# Optymalne dystanse walki per broń (dla MAINTAIN_DIST)
# scroll ma zasięg 1 — is_in_range sprawdza tylko 1 kratkę do przodu,
# więc optimal=2 nigdy nie odpala auto-ataku. Ustawiamy 1.
_WEAPON_OPTIMAL_RANGE = {
    'knife': 1, 'axe': 1, 'sword': 2,
    'bow': 5, 'amulet': 1, 'scroll': 1,
}


# ═══════════════════════════════════════════════════════════════════════════
#  Kontroler Pudzian
# ═══════════════════════════════════════════════════════════════════════════

class Pudzian(controller.Controller):
    """Główny kontroler bota Pudzian z DQN i pamięcią mapy."""

    def __init__(
        self,
        first_name: str = "Pudzian",
        brain_mode: str = "learner",
        transition_queue=None,
        device: Optional[str] = None,
        load_from_disk: bool = True,
    ):
        self.first_name = first_name
        self.is_evaluating = True # Domyślnie True, by python -m gupb nie robiło losowych ruchów
        self.heuristics = PudzianHeuristics()

        model_path = os.path.join(os.path.dirname(__file__), "pudzian_dqn.pt")
        self.brain = PudzianBrain(
            model_path,
            mode=brain_mode,
            transition_queue=transition_queue,
            device=device,
            load_from_disk=load_from_disk,
        )

        # Stan wewnętrzny
        self.turn_count: int = 0
        self.last_hp: int = 8
        self.last_weapon: str = 'knife'
        # Czy łuk był naładowany na początku tury (przed ewentualnym ATTACK).
        # Pierwszy ATTACK łukiem tylko ładuje (0 dmg) — bez tego nagroda
        # kredytowałaby ładowanie jak realny atak. Dla broni innych niż łuk
        # pole jest bez znaczenia (trzymamy True, by nie tłumić ich nagrody).
        self.last_bow_loaded: bool = True
        self.menhir_pos: Optional[coordinates.Coords] = None

        # Pamięć mapy — warstwa terenu (stała)
        self.terrain_memory: Dict[coordinates.Coords, str] = {}
        # Pamięć wrogów — krótkotrwała pamięć o pozycjach (object permanence)
        self._enemy_memory: Dict[coordinates.Coords, int] = {}
        # Licznik wizyt na polach (anty-oscylacja przy EXPLORE)
        self._visited_counter: Dict[coordinates.Coords, int] = {}
        # Licznik odkrytych kratek (do Intrinsic Reward)
        self._known_tiles_count: int = 0

        # Poprzedni stan i akcja (do treningu)
        self.last_state: Optional[torch.Tensor] = None
        self.last_tactic: Optional[int] = None
        self.last_mask: Optional[torch.Tensor] = None
        # Śledzenie akcji do nagrody za zabicie
        self.last_attacked: bool = False
        self.last_alive_count: Optional[int] = None
        self.last_enemy_in_range: bool = False
        self.last_weapon_upgrade_visible: bool = False
        self.mist_ever_seen: bool = False
        self.post_kill_potion_urge: int = 0
        # Licznik kolejnych SCAN — blokada anty-spam (stary model ma za wysokie Q dla SCAN)
        self._consecutive_scan: int = 0
        # Liczniki "stuck" — oddzielne dla potki i broni
        self._stuck_counter_potion: int = 0
        self._stuck_counter_weapon: int = 0
        self._last_potion_target: Optional[coordinates.Coords] = None
        self._last_weapon_target: Optional[coordinates.Coords] = None
        # Taniec amuletu: tymczasowe upuszczenie amuletu do skanu w trybie EXPLORE
        # Fazy: 0=wyłącz, 1=idź_do_zamiany, 2=skanuj, 3=odchodzi_od_skrytki, 4=wracaj_po_amulet
        self._amulet_dance_phase: int = 0
        self._amulet_stash_pos: Optional[coordinates.Coords] = None
        self._amulet_off_stash_target: Optional[coordinates.Coords] = None
        self._scan_turns_remaining: int = 0
        self._amulet_dance_timeout: int = 0

    # ── Interfejs Controller ──────────────────────────────────────────

    def __eq__(self, other):
        return isinstance(other, Pudzian) and self.first_name == other.first_name

    def __hash__(self):
        return hash(self.first_name)

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PUDZIAN

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        """Resetuje stan bota przed nową grą."""
        self.turn_count = 0
        self.last_hp = 8
        self.last_weapon = 'knife'
        self.last_bow_loaded = True
        self.menhir_pos = None
        self.terrain_memory.clear()
        self._enemy_memory.clear()
        self._visited_counter.clear()
        self._known_tiles_count = 0
        self.last_state = None
        self.last_tactic = None
        self.last_mask = None
        self.last_attacked = False
        self.last_alive_count = None
        self.last_enemy_in_range = False
        self.last_weapon_upgrade_visible = False
        self.mist_ever_seen = False
        self.post_kill_potion_urge = 0
        self._consecutive_scan = 0
        self._stuck_counter_potion = 0
        self._stuck_counter_weapon = 0
        self._last_potion_target = None
        self._last_weapon_target = None
        self._amulet_dance_phase = 0
        self._amulet_stash_pos = None
        self._amulet_off_stash_target = None
        self._scan_turns_remaining = 0
        self._amulet_dance_timeout = 0
        self.brain.decay_epsilon()  # no-op, epsilon sterowany przez step_count
        self.brain.reset_nstep_buffer()  # bez mostkowania okna n-step między epizodami

    # ═══════════════════════════════════════════════════════════════════
    #  Główna pętla decyzyjna
    # ═══════════════════════════════════════════════════════════════════

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.turn_count += 1

        # Licznik odwiedzin (anty-oscylacja przy EXPLORE)
        self._visited_counter[knowledge.position] = (
            self._visited_counter.get(knowledge.position, 0) + 1
        )

        # 1. Aktualizuj pamięć mapy i menhir
        new_tiles = self._update_map_memory(knowledge)

        # Raz zobaczona mgła → trwała flaga (wyłącza nagrodę za eksplorację)
        if not self.mist_ever_seen:
            me_tile = knowledge.visible_tiles.get(knowledge.position)
            if me_tile and any(eff.type == 'mist' for eff in me_tile.effects):
                self.mist_ever_seen = True
            elif any(
                any(eff.type == 'mist' for eff in tile.effects)
                for tile in knowledge.visible_tiles.values()
            ):
                self.mist_ever_seen = True

        # 1b. Aktualizuj pamięć o wrogach (object permanence)
        current_enemies = self._visible_enemies(knowledge)
        for pos in list(self._enemy_memory.keys()):
            if pos in knowledge.visible_tiles:
                tile = knowledge.visible_tiles[pos]
                if not tile.character or pos == knowledge.position:
                    del self._enemy_memory[pos]
        for pos in current_enemies:
            self._enemy_memory[pos] = self.turn_count
        for pos in list(self._enemy_memory.keys()):
            if self.turn_count - self._enemy_memory[pos] > 3:
                del self._enemy_memory[pos]

        # 1c. Zapisz poprzednie wartości (kontekst reward dla akcji z TAMTEJ tury),
        #     następnie odśwież last_hp/last_weapon by ekstrakcja stanu i maska
        #     używały AKTUALNEJ broni (a nie z poprzedniej tury).
        prev_hp = self.last_hp
        prev_weapon = self.last_weapon
        prev_weapon_upgrade_visible = self.last_weapon_upgrade_visible
        prev_bow_loaded = self.last_bow_loaded

        me_tile = knowledge.visible_tiles.get(knowledge.position)
        if me_tile and me_tile.character:
            self.last_hp = me_tile.character.health
            raw = me_tile.character.weapon.name
            self.last_weapon = 'bow' if raw.startswith('bow') else raw
            # Stan łuku PRZED akcją tej tury (nazwa w grze: bow_loaded/bow_unloaded).
            # Dla broni innych niż łuk trzymamy True (pole nieistotne).
            self.last_bow_loaded = (not raw.startswith('bow')) or raw.endswith('_loaded')

        self.last_weapon_upgrade_visible = self.heuristics.find_weapon_upgrade(
            knowledge.position, knowledge, self.last_weapon, self.terrain_memory
        ) is not None

        # 2. Wyciągnij bieżący stan i maskę
        curr_state = self._extract_state(knowledge)
        curr_mask = self._compute_action_mask(knowledge)

        # 3. Nagrodź poprzednią decyzję (kontekst z poprzedniej tury)
        if self.last_state is not None and self.last_tactic is not None and not self.is_evaluating:
            ctx = RewardContext(
                last_hp=prev_hp,
                last_weapon=prev_weapon,
                last_tactic=self.last_tactic,
                last_attacked=self.last_attacked,
                last_enemy_in_range=self.last_enemy_in_range,
                last_alive_count=self.last_alive_count,
                menhir_pos=self.menhir_pos,
                last_weapon_upgrade_visible=prev_weapon_upgrade_visible,
                mist_ever_seen=self.mist_ever_seen,
                last_bow_loaded=prev_bow_loaded,
            )
            reward = compute_reward(knowledge, new_tiles, ctx, self.heuristics)
            self.brain.store_transition(
                self.last_state, self.last_tactic, reward,
                curr_state, False, curr_mask,
            )
            self.brain.train_step()

        # 4. Wybierz mikro-taktykę i rozstrzygnij ewentualny override mgły
        chosen_tactic = self.brain.choose_action(curr_state, curr_mask, greedy=self.is_evaluating)
        tactic = self._resolve_tactic_with_safeguard(chosen_tactic, knowledge)

        # 5. Zapamiętaj na następną turę (hp/weapon już zaktualizowane w 1c)
        alive_now = knowledge.no_of_champions_alive
        if self.last_alive_count is not None and alive_now < self.last_alive_count:
            # Ktoś zginął. Byliśmy zaangażowani w walkę?
            if self.last_attacked or self.last_enemy_in_range:
                self.post_kill_potion_urge = 15  # Przez 15 tur mamy "głód" mikstury

        if self.last_hp >= 8:
            self.post_kill_potion_urge = 0

        self.last_state = curr_state
        self.last_tactic = tactic
        self.last_mask = curr_mask
        self.last_alive_count = alive_now

        # Licznik kolejnych SCAN-ów do blokady spamu w masce
        if tactic == Tactic.SCAN:
            self._consecutive_scan += 1
        else:
            self._consecutive_scan = 0

        # Taniec amuletu — override gdy aktywny
        if self._amulet_dance_phase > 0:
            if self._visible_enemies(knowledge):
                self._amulet_dance_phase = 0
                self._amulet_stash_pos = None
                self._amulet_off_stash_target = None
                self._amulet_dance_timeout = 0
            else:
                action = self._amulet_dance_step(knowledge)
                self.last_attacked = False
                self.last_enemy_in_range = False
                # Akcja tańca NIE jest tym, co wybrał DQN. Czyścimy
                # last_state/last_tactic, aby w następnej turze pominąć
                # store_transition — inaczej Q-update przypisałby reward
                # wykonanej akcji dance do wybranej (lecz nieużytej) taktyki.
                self.last_state = None
                self.last_tactic = None
                return action

        # 6. Wykonaj taktykę i zapamiętaj czy zaatakowaliśmy w zasięgu
        action = self._execute_tactic(tactic, knowledge)
        self.last_attacked = (action == characters.Action.ATTACK)

        # 7. Zaktualizuj last_enemy_in_range — czy wróg był w zasięgu PRZED atakiem
        enemies_now = self._visible_enemies(knowledge)
        if self.last_attacked and enemies_now:
            facing = self.heuristics.get_facing(knowledge)
            if facing:
                nearest = min(enemies_now, key=lambda p: self.heuristics.dist(knowledge.position, p))
                self.last_enemy_in_range = self.heuristics.is_in_range(
                    knowledge.position,
                    nearest,
                    facing,
                    self.last_weapon,
                    knowledge,
                    self.terrain_memory,
                )
            else:
                self.last_enemy_in_range = False
        else:
            self.last_enemy_in_range = False

        return action

    def praise(self, score: int) -> None:
        """Nagroda końcowa po zakończeniu gry.

        Oczekuje SYGNOWANEGO score: ujemne dla niskiego placementu,
        dodatnie dla wysokiego. train.py wysyła wartości w zakresie ~[-30, +30].
        """
        if self.is_evaluating:
            return
            
        if self.last_state is not None and self.last_tactic is not None:
            terminal_reward = float(score)
            # Zapisz terminalne przejście
            dummy_next = torch.zeros(39)
            dummy_mask = torch.ones(N_TACTICS)
            self.brain.store_transition(
                self.last_state, self.last_tactic, terminal_reward,
                dummy_next, True, dummy_mask,
            )
            self.brain.train_step()
        self.brain.save()

    # ═══════════════════════════════════════════════════════════════════
    #  Pamięć mapy (Map Memory)
    # ═══════════════════════════════════════════════════════════════════

    def _update_map_memory(self, knowledge: characters.ChampionKnowledge) -> int:
        """Aktualizuje pamięć terenu. Zwraca liczbę nowo odkrytych kratek."""
        new_count = 0
        for pos, tile in knowledge.visible_tiles.items():
            if pos not in self.terrain_memory:
                new_count += 1

            # Zapamiętaj menhir (priorytet — nigdy nie nadpisujemy go mgłą).
            if tile.type == 'menhir':
                self.menhir_pos = pos
                self.terrain_memory[pos] = 'menhir'
                continue

            # Mgła jest monotoniczna (nigdy nie ustępuje) → utrwalamy ją jako
            # pole nieprzejezdne, by pathfinding omijał strefę śmierci także
            # poza polem widzenia. Ognia NIE utrwalamy (jest tymczasowy —
            # unikany tylko gdy aktualnie widoczny, w _build_walkable).
            if any(eff.type == 'mist' for eff in tile.effects):
                self.terrain_memory[pos] = 'mist'
            else:
                self.terrain_memory[pos] = tile.type

        self._known_tiles_count += new_count
        return new_count

    # ═══════════════════════════════════════════════════════════════════
    #  Ekstrakcja stanu (34 cechy znormalizowane)
    # ═══════════════════════════════════════════════════════════════════

    def _extract_state(self, knowledge: characters.ChampionKnowledge) -> torch.Tensor:
        """Buduje 39-wymiarowy wektor stanu z bieżącej wiedzy.

        Zasady normalizacji:
          * Dystanse taktyczne (wrogowie, mikstury, broń): /15.0
            — zakres 0–15 kratek pokrywa 95% istotnych sytuacji,
            sieć wyraźnie rozróżnia zasięg noża (1) od łuku (5).
          * Dystanse strategiczne (menhir, mgła): /15.0
          * Kierunki relatywne: /15.0, clamp do [-1, 1]
          * HP: /8.0 (max HP)
          * Broń wroga: one-hot (6 cech)
        """
        state = torch.zeros(39, dtype=torch.float32)

        me_tile = knowledge.visible_tiles.get(knowledge.position)
        me_char = me_tile.character if me_tile else None

        # ── Własny stan (indeksy 0–10) ──
        hp = me_char.health if me_char else self.last_hp
        state[0] = hp / 8.0

        # Broń (one-hot, indeksy 1–6)
        raw_weapon = me_char.weapon.name if me_char else self.last_weapon
        weapon_name = 'bow' if raw_weapon.startswith('bow') else raw_weapon
        weapon_idx = {'knife': 1, 'sword': 2, 'axe': 3, 'bow': 4, 'amulet': 5, 'scroll': 6}
        state[weapon_idx.get(weapon_name, 1)] = 1.0

        # [34] Łuk naładowany? Pierwszy ATTACK tylko ładuje (bez obrażeń),
        # dopiero drugi strzela — bez tej cechy sieć nie odróżnia "strzelać"
        # od "tylko naciągam". Nazwa w grze to 'bow_loaded'/'bow_unloaded'
        # (uwaga: 'loaded' jest podłańcuchem 'unloaded' → używamy endswith).
        # Slot zarezerwowany (34) — wymiar stanu pozostaje 39, checkpoint zgodny.
        state[34] = 1.0 if raw_weapon.endswith('_loaded') else 0.0

        # Facing (one-hot, indeksy 7–10)
        if me_char:
            facing_map = {
                characters.Facing.UP: 7,
                characters.Facing.DOWN: 8,
                characters.Facing.LEFT: 9,
                characters.Facing.RIGHT: 10,
            }
            state[facing_map.get(me_char.facing, 7)] = 1.0

        # ── Najbliższy wróg (indeksy 11–16) ──
        enemies = self._known_enemies()
        if enemies:
            nearest = min(enemies, key=lambda p: self.heuristics.dist(knowledge.position, p))
            n_tile = knowledge.visible_tiles.get(nearest)
            n_char = n_tile.character if n_tile else None

            dist_to_nearest = self.heuristics.dist(knowledge.position, nearest)
            # /15.0 zamiast /50.0 — wróg na dystansie 3 = 0.2, na dystansie 8 = 0.53
            # Sieć wyraźnie rozróżnia zasięg noża (1) od miecza (2) od łuku (5).
            state[11] = min(dist_to_nearest / 15.0, 1.0)

            if n_char:
                state[12] = n_char.health / 8.0
                # Tier broni wroga zamiast binarnego "ma bow/scroll?"
                # Daje sieci informację czy wróg jest groźny (miecz vs nóż).
                enemy_weapon_raw = n_char.weapon.name
                enemy_weapon_norm = 'bow' if enemy_weapon_raw.startswith('bow') else enemy_weapon_raw
                state[13] = _WEAPON_TIERS.get(enemy_weapon_norm, 0) / 2.0
                state[14] = 1.0 if self.heuristics.enemy_facing_towards(
                    knowledge.position, nearest, n_char.facing
                ) else 0.0

            # Kierunek do wroga — /15.0 dla lepszej rozdzielczości
            state[15] = max(-1.0, min(1.0, (nearest[0] - knowledge.position[0]) / 15.0))
            state[16] = max(-1.0, min(1.0, (nearest[1] - knowledge.position[1]) / 15.0))

        # ── Najsłabszy wróg (indeksy 17–18) ──
        if enemies:
            enemy_chars = []
            for epos in enemies:
                et = knowledge.visible_tiles.get(epos)
                if et and et.character:
                    enemy_chars.append((epos, et.character))
            if enemy_chars:
                weakest_pos, weakest_char = min(enemy_chars, key=lambda x: x[1].health)
                state[17] = weakest_char.health / 8.0
                state[18] = min(self.heuristics.dist(knowledge.position, weakest_pos) / 15.0, 1.0)

        # ── Otoczenie (indeksy 19–25) ──
        state[19] = 1.0 if self.menhir_pos is not None else 0.0
        if self.menhir_pos:
            state[20] = min(self.heuristics.dist(knowledge.position, self.menhir_pos) / 15.0, 1.0)

        potion_pos = self.heuristics.find_potion(knowledge, self.terrain_memory, allow_unknown=True)
        if potion_pos:
            state[21] = min(self.heuristics.dist(knowledge.position, potion_pos) / 15.0, 1.0)

        weapon_pos = self.heuristics.find_weapon_upgrade(
            knowledge.position, knowledge, self.last_weapon, self.terrain_memory, allow_unknown=True
        )
        if weapon_pos:
            state[22] = min(self.heuristics.dist(knowledge.position, weapon_pos) / 15.0, 1.0)

        me_effects = me_tile.effects if me_tile else []
        state[23] = 1.0 if any(eff.type == 'mist' for eff in me_effects) else 0.0

        mist_tiles = [pos for pos, tile in knowledge.visible_tiles.items()
                      if any(eff.type == 'mist' for eff in tile.effects)]
        if mist_tiles:
            min_mist_dist = min(self.heuristics.dist(knowledge.position, m) for m in mist_tiles)
            # /15.0 — spójna skala z resztą dystansów
            state[24] = min(min_mist_dist / 15.0, 1.0)

        state[25] = min(len(enemies) / 10.0, 1.0) if enemies else 0.0

        # ── Kontekst gry (indeksy 26–29) ──
        state[26] = knowledge.no_of_champions_alive / 11.0
        state[27] = min(self.turn_count / 300.0, 1.0)
        # [28] Proporcja odkrytej mapy zamiast absolutnej pozycji X
        # — bardziej informatywne niż pozycja, bo informuje sieć
        # o stopniu eksploracji (czy warto dalej EXPLORE vs. walczyć).
        state[28] = min(self._known_tiles_count / 500.0, 1.0)
        # [29] Czy mgła jest blisko menhiru — kluczowy sygnał taktyczny.
        # Gdy mgła zbliża się do menhiru, bot powinien rzucić walkę
        # i biec do bezpiecznej strefy.
        if self.menhir_pos and mist_tiles:
            mist_to_menhir = min(self.heuristics.dist(self.menhir_pos, m) for m in mist_tiles)
            state[29] = 1.0 - min(mist_to_menhir / 15.0, 1.0)  # 1.0 = mgła NA menhirze
        else:
            state[29] = 0.0

        # ── Kompas mgły (indeksy 30–31) ──
        compass_x, compass_y = self.heuristics.compute_mist_compass(knowledge)
        state[30] = compass_x
        state[31] = compass_y

        # ── Kierunek do menhiru (indeksy 32–33) ──
        if self.menhir_pos:
            state[32] = max(-1.0, min(1.0, (self.menhir_pos[0] - knowledge.position[0]) / 15.0))
            state[33] = max(-1.0, min(1.0, (self.menhir_pos[1] - knowledge.position[1]) / 15.0))

        return state

    # ═══════════════════════════════════════════════════════════════════
    #  Action Masking
    # ═══════════════════════════════════════════════════════════════════

    def _compute_action_mask(self, knowledge: characters.ChampionKnowledge) -> torch.Tensor:
        """Oblicza maskę legalnych mikro-taktyk (14 boolów)."""
        mask = torch.zeros(N_TACTICS, dtype=torch.float32)

        # KRYTYCZNE: stoimy W mgle → tylko FOLLOW_MIST.
        # DQN nie może wybrać samobójstwa; reward jest naturalnie przypisany
        # do FOLLOW_MIST, bo to jedyny legalny wybór — sieć uczy się
        # prawidłowej polityki w mgle zamiast polegać na bezpieczniku.
        me_tile_mask = knowledge.visible_tiles.get(knowledge.position)
        me_effects_mask = me_tile_mask.effects if me_tile_mask else []
        if any(eff.type == 'mist' for eff in me_effects_mask):
            mask[Tactic.FOLLOW_MIST] = 1.0
            return mask

        # Mgła w polu widzenia — zbieramy raz i reużywamy.
        mist_positions = [
            pos for pos, tile in knowledge.visible_tiles.items()
            if any(eff.type == 'mist' for eff in tile.effects)
        ]
        has_mist = len(mist_positions) > 0
        # "Mist emergency" — mgła ≤3 kratek. Maska musi pokrywać się z
        # _resolve_tactic_with_safeguard, inaczej DQN może wybrać taktykę,
        # która jest natychmiast nadpisywana na FOLLOW_MIST → Q-value dla
        # wybranej akcji nigdy się nie aktualizuje → sieć utyka w preferencji
        # nielegalnej akcji.
        mist_emergency = False
        if mist_positions:
            min_mist_dist = min(
                self.heuristics.dist(knowledge.position, m) for m in mist_positions
            )
            mist_emergency = min_mist_dist <= 3

        enemies = self._known_enemies()
        has_enemy = len(enemies) > 0
        has_potion = self.heuristics.find_potion(
            knowledge, self.terrain_memory, allow_unknown=True
        ) is not None
        has_weapon = self.heuristics.find_weapon_upgrade(
            knowledge.position, knowledge, self.last_weapon, self.terrain_memory, allow_unknown=True
        ) is not None
        menhir_known = self.menhir_pos is not None

        # Sprawdź czy wróg jest faktycznie OSIĄGALNY lub możliwy do trafienia z miejsca.
        # Wróg może być widoczny przez wodę (sea jest transparent dla LOS),
        # ale fizycznie nieosiągalny BFS-em. Taktyki nawigacyjne (APPROACH,
        # ALIGN_AXIS, MAINTAIN_DIST) nie mogą znaleźć ścieżki → zwracają TURN_LEFT,
        # co powoduje oscylację lewo-prawo. Dzielimy taktyki na:
        #   • nawigacyjne (enemy_reachable): wymagają ścieżki lub zasięgu broni
        #   • mobilne (has_enemy): unik/ucieczka sensowne nawet przez wodę (wróg może mieć łuk)
        enemy_reachable = False
        if has_enemy:
            nearest = min(enemies, key=lambda p: self.heuristics.dist(knowledge.position, p))
            if self._enemy_attackable_from_here(knowledge, nearest):
                enemy_reachable = True
            else:
                path = self.heuristics.find_path(
                    knowledge.position, nearest, knowledge, self.terrain_memory
                )
                enemy_reachable = len(path) > 1

        # Taktyki nawigacyjne — tylko gdy wróg jest osiągalny lub w zasięgu
        if enemy_reachable:
            mask[Tactic.APPROACH] = 1.0
            mask[Tactic.ALIGN_AXIS] = 1.0
            mask[Tactic.MAINTAIN_DIST] = 1.0

        # Taktyki mobilne — gdy wróg widoczny (nawet przez wodę, może mieć łuk).
        # Dodatkowo sprawdzamy, czy dany ruch jest fizycznie możliwy — inaczej
        # bot przy ścianie wybiera DODGE/FLEE w kółko, heurystyka zwraca TURN
        # bo wszystkie ruchy zablokowane, anti-oscylacja blokuje przeciwny
        # DODGE, ale FLEE/SCAN/EXPLORE też zwracają TURN. Klasyczna pętla.
        if has_enemy:
            nearest_pos = min(enemies, key=lambda p: self.heuristics.dist(knowledge.position, p))
            dx = nearest_pos[0] - knowledge.position[0]
            dy = nearest_pos[1] - knowledge.position[1]

            # Mirror logiki z dodge_perpendicular — pole prostopadłe do osi.
            if abs(dx) > abs(dy):
                perp_left_off = (0, -1 if dx > 0 else 1)
                perp_right_off = (0, 1 if dx > 0 else -1)
            else:
                perp_left_off = (1 if dy > 0 else -1, 0)
                perp_right_off = (-1 if dy > 0 else 1, 0)

            perp_left = coordinates.Coords(
                knowledge.position[0] + perp_left_off[0],
                knowledge.position[1] + perp_left_off[1],
            )
            perp_right = coordinates.Coords(
                knowledge.position[0] + perp_right_off[0],
                knowledge.position[1] + perp_right_off[1],
            )

            if self._is_walkable_neighbor(perp_left, knowledge):
                mask[Tactic.DODGE_LEFT] = 1.0
            if self._is_walkable_neighbor(perp_right, knowledge):
                mask[Tactic.DODGE_RIGHT] = 1.0

            # FLEE_CLOSEST: tylko gdy jest sąsiad oddalający od wroga.
            current_dist = self.heuristics.dist(knowledge.position, nearest_pos)
            for ddx, ddy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                neighbor = coordinates.Coords(
                    knowledge.position[0] + ddx,
                    knowledge.position[1] + ddy,
                )
                if (
                    self._is_walkable_neighbor(neighbor, knowledge)
                    and self.heuristics.dist(neighbor, nearest_pos) > current_dist
                ):
                    mask[Tactic.FLEE_CLOSEST] = 1.0
                    break

        # Taktyki zasobowe — wymagają widocznych zasobów
        if has_potion:
            mask[Tactic.GET_POTION] = 1.0
        if has_weapon:
            mask[Tactic.GET_WEAPON] = 1.0

        # Taktyki pozycyjne
        if menhir_known:
            mask[Tactic.HOLD_MENHIR] = 1.0
        if has_mist:
            mask[Tactic.FOLLOW_MIST] = 1.0

        # Surowy ATTACK — legalny gdy jest po co machać: znany wróg (cios w
        # zapamiętanego/widocznego, nawet poza idealnym alignem) lub nienaciągnięty
        # łuk (proaktywne naciągnięcie cięciwy zanim wróg wejdzie w zasięg).
        # Pusty cios daje 0 nagrody (reward.py gate'uje +1.0 przez enemy_in_range),
        # więc sieć sama nauczy się nie machać w próżnię.
        if has_enemy or (self.last_weapon == 'bow' and not self.last_bow_loaded):
            mask[Tactic.ATTACK] = 1.0

        # WAIT (zasadzka) — tylko gdy jest kogo przeczekać. Bez wroga stanie w
        # miejscu jest czystą stratą tury, więc nie udostępniamy go w pustym polu
        # (od mapowania jest EXPLORE). DO_NOTHING nie ma nagrody bazowej za
        # przeżycie, więc nie grozi farmem pasywności.
        if has_enemy:
            mask[Tactic.WAIT] = 1.0

        # Eksploracja dostępna gdy brak OSIĄGALNEGO wroga.
        # Gdy wróg jest przez wodę (nieosiągalny), bot eksploruje by znaleźć
        # drogę dookoła — zamiast kręcić się w miejscu wywołując APPROACH.
        if not enemy_reachable:
            mask[Tactic.EXPLORE] = 1.0
            if self.last_weapon == 'amulet' or self.turn_count % 5 == 0:
                mask[Tactic.SCAN] = 1.0

        # Anti-spam SCAN: blokujemy gdy w ostatnich 2 turach był SCAN.
        # Stary checkpoint ma przeszacowane Q dla SCAN; ten guard daje sieci
        # szansę zaktualizować Q innych akcji zamiast spamować obroty.
        if self._consecutive_scan >= 2:
            mask[Tactic.SCAN] = 0.0

        # Anti-oscylacja DODGE_LEFT ↔ DODGE_RIGHT.
        if self.last_tactic == int(Tactic.DODGE_LEFT):
            mask[Tactic.DODGE_RIGHT] = 0.0
        elif self.last_tactic == int(Tactic.DODGE_RIGHT):
            mask[Tactic.DODGE_LEFT] = 0.0

        # Mist emergency override — musi być po pełnym wyliczeniu maski.
        # Pokrywamy się z _resolve_tactic_with_safeguard: gdy mgła ≤3 kratek,
        # tylko APPROACH/ALIGN_AXIS/FOLLOW_MIST są legalne. Dzięki temu DQN
        # nie wybiera akcji, które byłyby natychmiast nadpisywane (Q-update
        # przypisałby reward FOLLOW_MIST do faktycznego wyboru sieci).
        if mist_emergency:
            for t in Tactic:
                if t not in (Tactic.APPROACH, Tactic.ALIGN_AXIS, Tactic.FOLLOW_MIST):
                    mask[int(t)] = 0.0
            mask[Tactic.FOLLOW_MIST] = 1.0

        # Awaryjny fallback gdy maska całkowicie pusta.
        if mask.sum().item() == 0:
            if enemy_reachable:
                mask[Tactic.APPROACH] = 1.0
            else:
                mask[Tactic.EXPLORE] = 1.0

        return mask

    # Logika nagrody przeniesiona do reward.py (compute_reward / RewardContext).

    # ═══════════════════════════════════════════════════════════════════
    #  Bezpiecznik mgły — rozstrzyga FAKTYCZNĄ taktykę
    # ═══════════════════════════════════════════════════════════════════

    def _resolve_tactic_with_safeguard(
        self,
        tactic: int,
        knowledge: characters.ChampionKnowledge,
    ) -> int:
        """Zwraca taktykę, którą faktycznie wykonamy po bezpieczniku mgły.

        Maska blokuje wszystko poza FOLLOW_MIST gdy bot stoi W mgle, więc
        gałąź `in_mist` to defense-in-depth. Gałąź ≤3 jest aktywna — maska
        tam jest permisywna, więc DQN może wybrać np. DODGE/SCAN, a my
        nadpisujemy na FOLLOW_MIST. Zwracamy nową taktykę, by reward.py
        liczył nagrodę za to, co RZECZYWIŚCIE zrobiliśmy.
        """
        me_tile = knowledge.visible_tiles.get(knowledge.position)
        me_effects = me_tile.effects if me_tile else []
        in_mist = any(eff.type == 'mist' for eff in me_effects)
        if in_mist:
            return int(Tactic.FOLLOW_MIST)

        mist_positions = [
            pos for pos, tile in knowledge.visible_tiles.items()
            if any(eff.type == 'mist' for eff in tile.effects)
        ]
        if mist_positions:
            min_mist_dist = min(
                self.heuristics.dist(knowledge.position, m) for m in mist_positions
            )
            if min_mist_dist <= 3 and tactic not in (Tactic.APPROACH, Tactic.ALIGN_AXIS):
                return int(Tactic.FOLLOW_MIST)

        return tactic

    # ═══════════════════════════════════════════════════════════════════
    #  Dispatcher taktyk
    # ═══════════════════════════════════════════════════════════════════

    def _execute_tactic(self, tactic: int, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Przekłada wybraną mikro-taktykę na akcję gry."""

        # Auto-atak: jeśli wróg jest w zasięgu i taktyka jest ofensywna, atakuj
        if tactic in (Tactic.APPROACH, Tactic.ALIGN_AXIS, Tactic.MAINTAIN_DIST):
            enemies = self._visible_enemies(knowledge)
            if enemies:
                nearest = min(enemies, key=lambda p: self.heuristics.dist(knowledge.position, p))
                facing = self.heuristics.get_facing(knowledge)
                if facing and self.heuristics.is_in_range(
                    knowledge.position,
                    nearest,
                    facing,
                    self.last_weapon,
                    knowledge,
                    self.terrain_memory,
                ):
                    return characters.Action.ATTACK

        # Auto-Leczenie (Bezpiecznik po walce)
        # Jeśli niedawno kogoś zabiliśmy, brakuje nam HP i widzimy potkę -> ignorujemy sieć, rzucamy wszystko i pijemy
        if getattr(self, 'post_kill_potion_urge', 0) > 0 and self.last_hp < 8:
            self.post_kill_potion_urge -= 1
            if self.heuristics.find_potion(knowledge, self.terrain_memory, allow_unknown=True) is not None:
                return self._tactic_get_potion(knowledge)

        # Bezpiecznik mgły rozstrzyga się przed wywołaniem _execute_tactic
        # (zob. _resolve_tactic_with_safeguard wywołane w decide()).

        # Dispatcher
        if tactic == Tactic.APPROACH:
            return self._tactic_approach(knowledge)
        elif tactic == Tactic.ALIGN_AXIS:
            return self._tactic_align_axis(knowledge)
        elif tactic == Tactic.MAINTAIN_DIST:
            return self._tactic_maintain_dist(knowledge)
        elif tactic == Tactic.DODGE_LEFT:
            return self._tactic_dodge(knowledge, 'left')
        elif tactic == Tactic.DODGE_RIGHT:
            return self._tactic_dodge(knowledge, 'right')
        elif tactic == Tactic.FLEE_CLOSEST:
            return self._tactic_flee(knowledge)
        elif tactic == Tactic.GET_POTION:
            return self._tactic_get_potion(knowledge)
        elif tactic == Tactic.GET_WEAPON:
            return self._tactic_get_weapon(knowledge)
        elif tactic == Tactic.HOLD_MENHIR:
            return self._tactic_hold_menhir(knowledge)
        elif tactic == Tactic.FOLLOW_MIST:
            return self._tactic_follow_mist(knowledge)
        elif tactic == Tactic.EXPLORE:
            return self._tactic_explore(knowledge)
        elif tactic == Tactic.SCAN:
            return self._tactic_scan(knowledge)
        elif tactic == Tactic.ATTACK:
            # Surowy atak pod kontrolą sieci — sama decyduje o timingu
            # (naciągnięcie łuku, cios w zapamiętanego wroga za rogiem, bait).
            # Auto-atak wyżej obsługuje tylko taktyki nawigacyjne; tu bot bije
            # zawsze, gdy wybierze tę taktykę.
            return characters.Action.ATTACK
        elif tactic == Tactic.WAIT:
            # Świadome czekanie — zasadzka / nie zdradzanie pozycji ruchem.
            return characters.Action.DO_NOTHING
        else:
            return characters.Action.TURN_LEFT

    # ── Implementacje taktyk ──────────────────────────────────────────

    def _tactic_scan(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Skanuje mapę. Jeśli mamy amulet (ślepotę), upuszcza go wchodząc na inną broń."""
        if self.last_weapon == 'amulet':
            best_pos = None
            min_dist = float('inf')
            for pos, tile in knowledge.visible_tiles.items():
                if pos != knowledge.position and tile.loot and tile.loot.name != 'amulet':
                    d = self.heuristics.dist(knowledge.position, pos)
                    if d < min_dist:
                        path = self.heuristics.find_path(knowledge.position, pos, knowledge, self.terrain_memory)
                        if len(path) > 1:
                            min_dist = d
                            best_pos = pos
            if best_pos:
                return self.heuristics.move_towards(knowledge.position, best_pos, knowledge, self.terrain_memory)
            
            # W ostateczności idziemy w ciemno szukać jakiejś innej broni by porzucić amulet
            menhir_hint = self.menhir_pos or self.heuristics.estimate_menhir_from_mist(knowledge)
            frontier = self.heuristics.find_frontier(
                knowledge.position,
                knowledge,
                self.terrain_memory,
                visited_counter=self._visited_counter,
                menhir_hint=menhir_hint,
            )
            if frontier:
                return self.heuristics.move_towards(knowledge.position, frontier, knowledge, self.terrain_memory)
                
        return characters.Action.TURN_RIGHT

    def _tactic_approach(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Szarżuj na najbliższego wroga.

        APPROACH = atakuj/podejdź — NIGDY nie ucieka, nawet gdy "za blisko"
        względem optymalnego dystansu broni (od tego jest MAINTAIN_DIST).
        Wcześniej bot z mieczem (optimal=2) na dist=1 wywoływał move_away,
        mimo że miecz świetnie bije na 1 — w efekcie szarża stawała się
        ucieczką.
        """
        enemies = self._known_enemies()
        if not enemies:
            return characters.Action.TURN_LEFT
        target = min(enemies, key=lambda p: self.heuristics.dist(knowledge.position, p))

        optimal = _WEAPON_OPTIMAL_RANGE.get(self.last_weapon, 1)
        current_dist = self.heuristics.dist(knowledge.position, target)

        # W zasięgu pozycyjnym — wyrównaj do strzału (auto-atak już sprawdzony
        # wyżej w _execute_tactic; tu działamy gdy facing nie pasuje).
        if current_dist <= optimal + 2:
            if self.last_weapon == 'amulet':
                return self.heuristics.align_to_diagonal(
                    knowledge.position, target, knowledge, self.terrain_memory
                )
            if self.last_weapon == 'axe':
                return self.heuristics.align_to_adjacent(
                    knowledge.position, target, knowledge, self.terrain_memory
                )
            return self.heuristics.align_to_axis(
                knowledge.position, target, knowledge, self.terrain_memory, weapon_name=self.last_weapon
            )

        return self.heuristics.move_towards(
            knowledge.position, target, knowledge, self.terrain_memory
        )

    def _tactic_align_axis(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Ustaw się na osi strzału z najbliższym wrogiem.
        - Dla amuletu: wyrównuje się do przekątnej (kiedy w zasięgu)
        - Dla siekiery: wyrównuje się do przylegającego pola (kiedy w zasięgu)
        - Dla reszty: wyrównuje się do osi (kiedy w zasięgu)"""
        target = self._combat_target(knowledge)
        if target is None:
            return characters.Action.TURN_LEFT

        optimal = _WEAPON_OPTIMAL_RANGE.get(self.last_weapon, 1)
        current_dist = self.heuristics.dist(knowledge.position, target)
        
        # Jeśli zbyt daleko — najpierw podchodzim
        if current_dist > optimal + 2:
            return self.heuristics.move_towards(
                knowledge.position, target, knowledge, self.terrain_memory
            )
        
        # W zasięgu — wyrównaj się do odpowiedniej pozycji ataku
        if self.last_weapon == 'amulet':
            return self.heuristics.align_to_diagonal(
                knowledge.position, target, knowledge, self.terrain_memory
            )
        if self.last_weapon == 'axe':
            return self.heuristics.align_to_adjacent(
                knowledge.position, target, knowledge, self.terrain_memory
            )
        return self.heuristics.align_to_axis(
            knowledge.position, target, knowledge, self.terrain_memory, weapon_name=self.last_weapon
        )

    def _tactic_maintain_dist(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Utrzymuj optymalny dystans od wroga.

        Cała logika "za blisko / za daleko / w zakresie + align proper-for-weapon"
        żyje w heuristics.maintain_distance — tu tylko delegacja, by uniknąć
        duplikacji sprawdzania zakresu.
        """
        target = self._combat_target(knowledge)
        if target is None:
            return characters.Action.TURN_LEFT

        optimal = _WEAPON_OPTIMAL_RANGE.get(self.last_weapon, 1)
        return self.heuristics.maintain_distance(
            knowledge.position, target, optimal, knowledge, self.terrain_memory,
            weapon_name=self.last_weapon,
        )

    def _tactic_dodge(self, knowledge: characters.ChampionKnowledge, direction: str) -> characters.Action:
        """Unik prostopadły do osi z wrogiem."""
        enemies = self._known_enemies()
        if not enemies:
            return characters.Action.TURN_LEFT
        target = min(enemies, key=lambda p: self.heuristics.dist(knowledge.position, p))
        return self.heuristics.dodge_perpendicular(
            knowledge.position, target, direction, knowledge, self.terrain_memory
        )

    def _tactic_flee(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Uciekaj od najbliższego wroga."""
        enemies = self._known_enemies()
        if not enemies:
            return characters.Action.TURN_LEFT
        target = min(enemies, key=lambda p: self.heuristics.dist(knowledge.position, p))
        return self.heuristics.move_away(
            knowledge.position, target, knowledge, self.terrain_memory
        )

    def _tactic_get_potion(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Idź po najbliższą miksturę.

        Jeśli bot utknął (5+ tur bez wykonania kroku), porzuca cel i wraca do EXPLORE.
        """
        potion = self.heuristics.find_potion(knowledge, self.terrain_memory, allow_unknown=True)
        if potion:
            if self._last_potion_target != potion:
                self._stuck_counter_potion = 0
                self._last_potion_target = potion

            action = self.heuristics.move_towards(
                knowledge.position, potion, knowledge, self.terrain_memory, allow_unknown=True
            )

            # Stuck = same obroty (LEFT lub RIGHT) bez kroku. get_action_to_reach
            # może zwrócić TURN_RIGHT zależnie od orientacji — symetryczny
            # licznik łapie obie strony.
            if action in (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT):
                self._stuck_counter_potion += 1
                if self._stuck_counter_potion >= 5:
                    self._stuck_counter_potion = 0
                    self._last_potion_target = None
                    return self._tactic_explore(knowledge)
            else:
                self._stuck_counter_potion = 0

            return action

        self._stuck_counter_potion = 0
        self._last_potion_target = None
        return characters.Action.TURN_LEFT

    def _tactic_get_weapon(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Idź po upgrade broni.

        Jeśli bot utknął (5+ tur bez wykonania kroku), porzuca cel i wraca do EXPLORE.
        """
        weapon = self.heuristics.find_weapon_upgrade(
            knowledge.position, knowledge, self.last_weapon, self.terrain_memory, allow_unknown=True
        )
        if weapon:
            if self._last_weapon_target != weapon:
                self._stuck_counter_weapon = 0
                self._last_weapon_target = weapon

            action = self.heuristics.move_towards(
                knowledge.position, weapon, knowledge, self.terrain_memory, allow_unknown=True
            )

            # Stuck = same obroty (LEFT lub RIGHT) bez kroku. Symetryczny
            # licznik łapie obie strony — patrz _tactic_get_potion.
            if action in (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT):
                self._stuck_counter_weapon += 1
                if self._stuck_counter_weapon >= 5:
                    self._stuck_counter_weapon = 0
                    self._last_weapon_target = None
                    return self._tactic_explore(knowledge)
            else:
                self._stuck_counter_weapon = 0

            return action

        self._stuck_counter_weapon = 0
        self._last_weapon_target = None
        return characters.Action.TURN_LEFT

    def _tactic_hold_menhir(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Idź do menhiru i broń pozycji."""
        target = self.menhir_pos or coordinates.Coords(25, 25)
        dist_to_menhir = self.heuristics.dist(knowledge.position, target)

        # Jeśli blisko menhiru, atakuj intruzów
        enemies = self._visible_enemies(knowledge)
        if enemies and dist_to_menhir <= 3:
            nearest = min(enemies, key=lambda p: self.heuristics.dist(knowledge.position, p))
            facing = self.heuristics.get_facing(knowledge)
            if facing and self.heuristics.is_in_range(
                knowledge.position,
                nearest,
                facing,
                self.last_weapon,
                knowledge,
                self.terrain_memory,
            ):
                return characters.Action.ATTACK

        # Jeśli blisko, campuj
        if dist_to_menhir <= 2:
            return self.heuristics.camp()

        # W przeciwnym razie idź do menhiru
        return self.heuristics.move_towards(
            knowledge.position, target, knowledge, self.terrain_memory
        )

    def _tactic_follow_mist(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Uciekaj od mgły. KAŻDY fallback weryfikuje czy BFS znalazło ścieżkę
        — jeśli nie, przechodzi do kolejnego. Awaryjnie: krok w dowolną sąsiednią
        przejezdną kratkę. Bot NIGDY nie zostaje w miejscu rotując bez sensu."""

        def try_target(target: coordinates.Coords) -> Optional[characters.Action]:
            """Zwraca akcję jeśli BFS znalazło ścieżkę do celu, inaczej None."""
            path = self.heuristics.find_path(
                knowledge.position, target, knowledge, self.terrain_memory
            )
            if len(path) > 1:
                return self.heuristics.get_action_to_reach(
                    knowledge.position, path[1], knowledge
                )
            return None

        # 1. Znany menhir
        if self.menhir_pos:
            action = try_target(self.menhir_pos)
            if action is not None:
                return action

        # 2. Estymacja menhiru z geometrii mgły
        estimated = self.heuristics.estimate_menhir_from_mist(knowledge)
        if estimated is not None:
            action = try_target(estimated)
            if action is not None:
                return action

        # 3. Kompas — 10 kratek od centroidu mgły
        compass_x, compass_y = self.heuristics.compute_mist_compass(knowledge)
        if abs(compass_x) > 0.01 or abs(compass_y) > 0.01:
            target_x = int(knowledge.position[0] + compass_x * 10)
            target_y = int(knowledge.position[1] + compass_y * 10)
            action = try_target(coordinates.Coords(max(0, target_x), max(0, target_y)))
            if action is not None:
                return action

        # 4. Centrum mapy
        action = try_target(coordinates.Coords(25, 25))
        if action is not None:
            return action

        # 5. AWARYJNIE: dowolna sąsiednia przejezdna kratka (najlepiej bez mgły).
        # Pozwala wyrwać się z sytuacji "wszystkie cele BFS-em nieosiągalne".
        walkable_types = {'land', 'forest', 'menhir'}
        candidates_no_mist = []
        candidates_any = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            adj = coordinates.Coords(knowledge.position[0] + dx, knowledge.position[1] + dy)
            tile = knowledge.visible_tiles.get(adj)
            if tile and tile.type in walkable_types:
                has_mist = any(eff.type == 'mist' for eff in tile.effects)
                if has_mist:
                    candidates_any.append(adj)
                else:
                    candidates_no_mist.append(adj)
        pick = (candidates_no_mist or candidates_any)
        if pick:
            return self.heuristics.get_action_to_reach(knowledge.position, pick[0], knowledge)

        # 6. Beznadziejnie zablokowany — przynajmniej rotuj.
        return characters.Action.TURN_LEFT

    def _tactic_explore(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Idź w stronę nieodkrytych kratek. Jeśli mamy amulet, zainicjuj taniec wymiennego skanu."""
        if self.last_weapon == 'amulet' and self._amulet_dance_phase == 0:
            swap_target = self._find_any_weapon_for_swap(knowledge)
            if swap_target:
                self._amulet_dance_phase = 1
                self._amulet_stash_pos = swap_target
                self._amulet_dance_timeout = 25
                return self.heuristics.move_towards(
                    knowledge.position, swap_target, knowledge, self.terrain_memory
                )
        return self._tactic_explore_normal(knowledge)

    def _tactic_explore_normal(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Standardowa eksploracja bez logiki tańca amuletu."""
        potion = self.heuristics.find_potion(knowledge, self.terrain_memory, allow_unknown=True)
        if potion:
            return self.heuristics.move_towards(
                knowledge.position, potion, knowledge, self.terrain_memory, allow_unknown=True
            )

        # Frontier ważony: visited_counter (anty-oscylacja) + oszacowany menhir (bias kierunku).
        # Jeśli menhir znany — używamy go bezpośrednio; w przeciwnym razie próbujemy
        # oszacować z geometrii mgły (jeśli widać mgłę).
        menhir_hint = self.menhir_pos or self.heuristics.estimate_menhir_from_mist(knowledge)
        frontier = self.heuristics.find_frontier(
            knowledge.position,
            knowledge,
            self.terrain_memory,
            visited_counter=self._visited_counter,
            menhir_hint=menhir_hint,
        )
        if frontier:
            return self.heuristics.move_towards(
                knowledge.position, frontier, knowledge, self.terrain_memory, allow_unknown=True
            )
        return self.heuristics.move_towards(
            knowledge.position, coordinates.Coords(25, 25), knowledge, self.terrain_memory, allow_unknown=True
        )

    def _find_any_weapon_for_swap(
        self, knowledge: characters.ChampionKnowledge
    ) -> Optional[coordinates.Coords]:
        """Szuka najbliższej widocznej i osiągalnej broni do zamiany z amuletem."""
        best_pos = None
        min_dist = float('inf')
        for pos, tile in knowledge.visible_tiles.items():
            if pos == knowledge.position:
                continue
            if tile.loot and not tile.character:
                d = self.heuristics.dist(knowledge.position, pos)
                if d < min_dist:
                    path = self.heuristics.find_path(
                        knowledge.position, pos, knowledge, self.terrain_memory
                    )
                    if len(path) > 1:
                        min_dist = d
                        best_pos = pos
        return best_pos

    def _amulet_dance_step(
        self, knowledge: characters.ChampionKnowledge
    ) -> characters.Action:
        """Jeden krok maszyny stanów tańca amuletu: upuść → skanuj → podnieś."""
        _WALKABLE = {'land', 'forest', 'menhir'}

        self._amulet_dance_timeout -= 1
        if self._amulet_dance_timeout <= 0:
            self._amulet_dance_phase = 0
            self._amulet_stash_pos = None
            self._amulet_off_stash_target = None
            return self._tactic_explore_normal(knowledge)

        phase = self._amulet_dance_phase

        if phase == 1:  # Idź do broni — wymiana spowoduje upuszczenie amuletu
            if self.last_weapon != 'amulet':
                # Wymiana nastąpiła — start skanu
                self._amulet_dance_phase = 2
                self._scan_turns_remaining = 4
                return characters.Action.TURN_RIGHT
            if self._amulet_stash_pos:
                # Jeśli dotarliśmy do celu, ale wciąż mamy amulet — loot zniknął
                if knowledge.position == self._amulet_stash_pos:
                    self._amulet_dance_phase = 0
                    return self._tactic_explore_normal(knowledge)
                return self.heuristics.move_towards(
                    knowledge.position, self._amulet_stash_pos, knowledge, self.terrain_memory
                )
            self._amulet_dance_phase = 0
            return characters.Action.TURN_LEFT

        elif phase == 2:  # Skan — 4 obroty w miejscu
            if self._scan_turns_remaining > 0:
                self._scan_turns_remaining -= 1
                return characters.Action.TURN_RIGHT
            # Skan gotowy — znajdź sąsiednie pole do odejścia od skrytki
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                adj = coordinates.Coords(
                    knowledge.position[0] + dx,
                    knowledge.position[1] + dy
                )
                if adj == self._amulet_stash_pos:
                    continue
                tile = knowledge.visible_tiles.get(adj)
                if tile and tile.type in _WALKABLE and not tile.character:
                    self._amulet_off_stash_target = adj
                    self._amulet_dance_phase = 3
                    return self.heuristics.get_action_to_reach(
                        knowledge.position, adj, knowledge
                    )
            self._amulet_dance_phase = 0
            return characters.Action.TURN_LEFT

        elif phase == 3:  # Odchodzi od skrytki (musi wyjść by potem wejść i odebrać)
            if knowledge.position != self._amulet_stash_pos:
                self._amulet_dance_phase = 4
                return self.heuristics.move_towards(
                    knowledge.position, self._amulet_stash_pos, knowledge, self.terrain_memory
                )
            if self._amulet_off_stash_target:
                return self.heuristics.get_action_to_reach(
                    knowledge.position, self._amulet_off_stash_target, knowledge
                )
            self._amulet_dance_phase = 0
            return characters.Action.TURN_LEFT

        elif phase == 4:  # Wróć po amulet
            if self.last_weapon == 'amulet':
                self._amulet_dance_phase = 0
                self._amulet_stash_pos = None
                self._amulet_off_stash_target = None
                return self._tactic_explore_normal(knowledge)
            # Sprawdź czy amulet wciąż leży na skrytce (widoczna kratka)
            if self._amulet_stash_pos:
                stash_tile = knowledge.visible_tiles.get(self._amulet_stash_pos)
                if stash_tile and (not stash_tile.loot or stash_tile.loot.name != 'amulet'):
                    # Ktoś zabrał amulet — przerwij
                    self._amulet_dance_phase = 0
                    return self._tactic_explore_normal(knowledge)
                return self.heuristics.move_towards(
                    knowledge.position, self._amulet_stash_pos, knowledge, self.terrain_memory
                )
            self._amulet_dance_phase = 0
            return characters.Action.TURN_LEFT

        self._amulet_dance_phase = 0
        return characters.Action.TURN_LEFT

    # ── Helpery ───────────────────────────────────────────────────────

    def _visible_enemies(self, knowledge: characters.ChampionKnowledge) -> List:
        """Zwraca listę pozycji widocznych wrogów."""
        return [pos for pos, tile in knowledge.visible_tiles.items()
                if tile.character and pos != knowledge.position]

    def _known_enemies(self) -> List[coordinates.Coords]:
        """Zwraca listę pozycji wrogów (widocznych oraz z pamięci krótkotrwałej)."""
        return list(self._enemy_memory.keys())

    def _combat_target(
        self, knowledge: characters.ChampionKnowledge
    ) -> Optional[coordinates.Coords]:
        """Najbliższy cel do precyzyjnego pozycjonowania ataku.

        Preferuje wrogów AKTUALNIE widocznych — pozycjonowanie (ALIGN/MAINTAIN)
        ku „duchowi" z pamięci 3-turowej marnuje tury na ustawianie się do
        miejsca, gdzie wroga już nie ma. Dopiero gdy nikogo nie widać,
        spadamy na pamięć krótkotrwałą (object permanence) jak reszta taktyk.
        """
        visible = self._visible_enemies(knowledge)
        pool = visible if visible else self._known_enemies()
        if not pool:
            return None
        return min(pool, key=lambda p: self.heuristics.dist(knowledge.position, p))

    def _enemy_attackable_from_here(
        self,
        knowledge: characters.ChampionKnowledge,
        enemy_pos: coordinates.Coords,
    ) -> bool:
        """Czy wróg jest do trafienia po samym obrocie (bez ruchu)."""
        for facing in characters.Facing:
            if self.heuristics.is_in_range(
                knowledge.position,
                enemy_pos,
                facing,
                self.last_weapon,
                knowledge,
                self.terrain_memory,
            ):
                return True
        return False

    _WALKABLE_TYPES = {'land', 'forest', 'menhir'}

    def _is_walkable_neighbor(
        self,
        pos: coordinates.Coords,
        knowledge: characters.ChampionKnowledge,
    ) -> bool:
        """Czy pole jest przejezdne (teren + brak wroga)."""
        if pos in knowledge.visible_tiles:
            tile = knowledge.visible_tiles[pos]
            if tile.type not in self._WALKABLE_TYPES:
                return False
            if tile.character is not None and pos != knowledge.position:
                return False
            return True
        if pos in self.terrain_memory:
            return self.terrain_memory[pos] in self._WALKABLE_TYPES
        return False
