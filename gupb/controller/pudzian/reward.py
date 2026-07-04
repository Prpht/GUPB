"""
Moduł obliczania nagród dla agenta Pudzian.

Odpowiedzialność tego pliku:
  Wyłącznie obliczenie skalaru nagrody (reward) na podstawie
  przejścia (s, a, s') w środowisku. Żadna logika sterowania botem
  ani architektura sieci nie należy tu.

Publiczne API:
  RewardContext  — niezmienny snapshot stanu z poprzedniej tury
  compute_reward — czysta funkcja nagrody (bez efektów ubocznych)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from gupb.model import characters, coordinates
from gupb.controller.pudzian.heuristics import PudzianHeuristics, _WEAPON_TIERS
from gupb.controller.pudzian.tactics import Tactic


# Taktyki w których bot jest "zaangażowany w walkę" — nie powinien być karany
# za niewybranie GET_WEAPON nawet gdy lepsza broń jest widoczna.
_COMBAT_TACTICS = {
    Tactic.APPROACH, Tactic.ALIGN_AXIS, Tactic.MAINTAIN_DIST,
    Tactic.DODGE_LEFT, Tactic.DODGE_RIGHT, Tactic.FLEE_CLOSEST,
    Tactic.ATTACK,
}

# Taktyki pasywne przy menhirze — tylko one dostają menhir-hold reward.
# Bez tego ograniczenia bot dostawał +0.4/turę za STAN (bycie blisko menhira)
# niezależnie od decyzji, co prowadziło do farmu pasywności.
_MENHIR_HOLD_TACTICS = {Tactic.HOLD_MENHIR, Tactic.FOLLOW_MIST}


# ═══════════════════════════════════════════════════════════════════════════
#  Kontekst nagrody — snapshot poprzedniej tury
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RewardContext:
    """Niemutowalny snapshot stanu bota z końca poprzedniej tury.

    Przekazywany do compute_reward, by funkcja nie miała dostępu
    do żadnych mutowalnych pól Pudziana — czysty interfejs.

    Pola
    ----
    last_hp : int
        HP bota na koniec poprzedniej tury.
    last_weapon : str
        Znormalizowana nazwa broni ('bow' zamiast 'bow_loaded' itp.).
    last_tactic : int
        Indeks mikro-taktyki wybranej w poprzedniej turze.
    last_attacked : bool
        Czy poprzednia akcja to ATTACK.
    last_enemy_in_range : bool
        Czy w momencie ataku wróg był faktycznie w zasięgu broni.
    last_alive_count : Optional[int]
        Liczba żywych graczy na koniec poprzedniej tury.
    menhir_pos : Optional[coordinates.Coords]
        Ostatnia znana pozycja menhiru.
    """
    last_hp: int
    last_weapon: str
    last_tactic: int
    last_attacked: bool
    last_enemy_in_range: bool
    last_alive_count: Optional[int]
    menhir_pos: Optional[coordinates.Coords] = None
    last_weapon_upgrade_visible: bool = False
    mist_ever_seen: bool = False
    last_bow_loaded: bool = True


# ═══════════════════════════════════════════════════════════════════════════
#  Pomocnik — widoczni wrogowie
# ═══════════════════════════════════════════════════════════════════════════

def _visible_enemies(knowledge: characters.ChampionKnowledge) -> list:
    """Zwraca listę pozycji widocznych wrogów (bez własnej pozycji)."""
    return [
        pos for pos, tile in knowledge.visible_tiles.items()
        if tile.character and pos != knowledge.position
    ]


# ═══════════════════════════════════════════════════════════════════════════
#  Główna funkcja nagrody
# ═══════════════════════════════════════════════════════════════════════════

def compute_reward(
    knowledge: characters.ChampionKnowledge,
    new_tiles: int,
    ctx: RewardContext,
    heuristics: PudzianHeuristics,
) -> float:
    """Oblicza nagrodę za poprzedni krok bota.

    Parametry
    ---------
    knowledge : ChampionKnowledge
        Bieżąca wiedza bota (stan s').
    new_tiles : int
        Liczba nowo odkrytych kratek w tej turze.
    ctx : RewardContext
        Snapshot stanu bota z końca poprzedniej tury (stan s).
    heuristics : PudzianHeuristics
        Narzędzia do obliczeń przestrzennych (dist, itp.).

    Zwraca
    ------
    float
        Skalar nagrody za przejście (s, a) → s'.

    Projekt funkcji
    ---------------
    * Brak bazowej nagrody za przeżycie — zapobiega uczeniu się
      pasywności; bot jest nagradzany za DZIAŁANIA, nie za egzystencję.
    * Skala nagród: kara za mgłę (-1.5) + kara za HP (-1.5/HP)
      łącznie dają ~-3.0/turę w mgle — wystarczające do ucieczki,
      ale nie dominujące nad sygnałem terminalnym (±30).
    """
    reward = 0.0

    me_tile = knowledge.visible_tiles.get(knowledge.position)
    if not (me_tile and me_tile.character):
        # Brak danych o sobie — nie możemy obliczyć sensownej nagrody.
        return reward

    curr_hp = me_tile.character.health
    hp_delta = ctx.last_hp - curr_hp  # > 0 = obrażenia, < 0 = leczenie

    # Oblicz raz, używaj wielokrotnie
    enemies = _visible_enemies(knowledge)
    mist_tiles = [
        pos for pos, tile in knowledge.visible_tiles.items()
        if any(eff.type == 'mist' for eff in tile.effects)
    ]

    # ── Zmiany HP ────────────────────────────────────────────────────────
    if hp_delta > 0:
        reward -= hp_delta * 1.5         # kara za otrzymane obrażenia
    elif hp_delta < 0:
        reward += abs(hp_delta) * 0.75   # nagroda za leczenie (mniejsza niż kara)

    # ── Zabicie wroga (heurystyka) ────────────────────────────────────────
    # Warunek: zaatakowaliśmy, wróg był faktycznie w zasięgu, i ktoś zginął.
    # Wartość +10 sprawia, że nawet kill z 4 hitami obrażeń (-6) ma netto +4.
    #
    # Wymagamy `last_enemy_in_range=True` — bez tego bot dostawał +4.0 za
    # każde zabicie w turze, w której kliknął ATTACK poza zasięgiem (false
    # credit gdy inny bot dokonał killa). W multi-actor PvP to było realnym
    # źródłem zaszumienia gradientu.
    if (
        ctx.last_attacked
        and ctx.last_enemy_in_range
        and ctx.last_alive_count is not None
    ):
        killed = ctx.last_alive_count - knowledge.no_of_champions_alive
        if killed > 0:
            # Cap na 2 zabicia/turę — przy bow-line lub AOE potencjalnie ginie
            # wielu wrogów naraz. Bez capa pojedyncza tura mogła dawać +30
            # (tyle co terminal reward) i zaszumiać gradient.
            reward += 10.0 * min(killed, 2)

    # ── Nagroda za atak na wroga w zasięgu ───────────────────────────────
    # +1.0 (z 0.5) — per-turn sygnał wyraźnie wybija się ze szumu,
    # DQN uczy się że wymiana w walce się opłaca turę po turze.
    #
    # Wyjątek: pierwszy ATTACK łukiem tylko NACIĄGA cięciwę (0 obrażeń);
    # dopiero kolejny strzela. Nie nagradzamy naciągania jak realnej wymiany
    # — inaczej bot uczyłby się „klikać" łuk w zasięgu bez zadawania obrażeń.
    attack_dealt_damage = not (ctx.last_weapon == 'bow' and not ctx.last_bow_loaded)
    if ctx.last_attacked and ctx.last_enemy_in_range and attack_dealt_damage:
        reward += 1.0

    # ── Kara za stanie w mgle ─────────────────────────────────────────────
    # Łączna kara w mgle: -1.5 (kafelek) + -1.5*hp_delta (obrażenia) ≈ -3.0/turę.
    # Wartość -1.5 nie dominuje samodzielnie nad sygnałem terminalnym (±30).
    if any(eff.type == 'mist' for eff in me_tile.effects):
        reward -= 1.5

    # ── Kara za stanie w ogniu ────────────────────────────────────────────
    # Ogień zadaje 3 HP/turę (3x więcej niż mgła). hp_delta już daje -4.5,
    # ale to kara reaktywna — bot najpierw wchodzi, potem obrywa. Explicit
    # kara -3.0 sprawia że łączna kara wynosi ~-7.5/turę i jest wyraźnie
    # wyższa niż alternatywa (walka, eksploracja, mgła).
    if any(eff.type == 'fire' for eff in me_tile.effects):
        reward -= 3.0

    # ── Nagroda za upgrade broni ──────────────────────────────────────────
    # Proporcjonalna do skoku tiera: nóż→łuk = +4.0, nóż→topór = +2.0.
    # Flat +2.0 nie rozróżniało wartości broni — DQN traktował łuk tak samo
    # jak toporek, więc nie opłacało się specjalnie gonić za lepszą bronią.
    curr_weapon_raw = me_tile.character.weapon.name
    curr_weapon_norm = 'bow' if curr_weapon_raw.startswith('bow') else curr_weapon_raw
    tier_gain = _WEAPON_TIERS.get(curr_weapon_norm, 0) - _WEAPON_TIERS.get(ctx.last_weapon, 0)
    if tier_gain > 0:
        reward += tier_gain * 2.0

    # ── Kara za ignorowanie dostępnego upgradu broni ───────────────────────
    # Wyłączona w trakcie walki — bot słusznie atakujący/uciekający/unikający
    # nie powinien dostawać -0.3/turę za "ignorowanie broni" gdy ma immediate
    # combat priority. Wcześniej w długiej wymianie z wrogiem cumulative -1.5..-3.0
    # niwelowało +1.0 za atak w zasięgu.
    if (
        ctx.last_weapon_upgrade_visible
        and ctx.last_tactic != Tactic.GET_WEAPON
        and ctx.last_tactic not in _COMBAT_TACTICS
    ):
        reward -= 0.3

    # ── Kary za SCAN — marnowanie tury w różnych kontekstach ──────────────
    # Trzy poziomy:
    #   1. SCAN obok wroga (≤ 2 kratki) → -0.5 (kręci się w walce)
    #   2. SCAN bez nowych kafli → -0.1 (rotacja w znanym obszarze)
    #   3. SCAN bez nowych kafli + brak wrogów → dodatkowe -0.05
    #      (najgorszy przypadek: ani informacji, ani sygnału walki)
    if ctx.last_tactic == Tactic.SCAN:
        if enemies:
            nearest_dist = min(heuristics.dist(knowledge.position, p) for p in enemies)
            if nearest_dist <= 2:
                reward -= 0.5
        if new_tiles == 0:
            reward -= 0.1
            if not enemies:
                reward -= 0.05

    # ── Nagroda za skuteczny unik ─────────────────────────────────────────
    # Warunek: użyliśmy uniku, wróg był blisko (≤ 3), nie oberwaliśmy mocno.
    # `hp_delta <= 1` (a nie `== 0`) — bot mógł dostać 1 dmg od mgły jednocześnie
    # z udanym dodgem; nie chcemy karać go za "częściowy sukces".
    # Mała wartość (0.1) — kill (+10) i atak w zasięgu (+1.0) muszą być
    # wyraźnie atrakcyjniejsze niż pętla DODGE-LEFT ↔ DODGE-RIGHT.
    if hp_delta <= 1 and ctx.last_tactic in (Tactic.DODGE_LEFT, Tactic.DODGE_RIGHT):
        if enemies:
            nearest = min(enemies, key=lambda p: heuristics.dist(knowledge.position, p))
            if heuristics.dist(knowledge.position, nearest) <= 3:
                reward += 0.1

    # ── Nagroda za trzymanie menhiru gdy mgła jest blisko ─────────────────
    # Aktywna tylko gdy:
    #   - bot ŚWIADOMIE wybrał HOLD_MENHIR lub FOLLOW_MIST (nie farm pozycji),
    #   - mgła w zasięgu ≤ 4 kratek od bota,
    #   - bot jest faktycznie przy menhirze (≤ 3).
    # Wartość zmniejszona z 0.4 do 0.15 — wcześniej bot mógł nagarniać +0.4 × 30 turn
    # = +12 cumulative tylko za stanie, co przekraczało terminal placement reward.
    if (
        ctx.last_tactic in _MENHIR_HOLD_TACTICS
        and ctx.menhir_pos is not None
        and mist_tiles
    ):
        min_mist_dist = min(heuristics.dist(knowledge.position, m) for m in mist_tiles)
        if min_mist_dist <= 4:
            dist_to_menhir = heuristics.dist(knowledge.position, ctx.menhir_pos)
            if dist_to_menhir <= 3:
                reward += 0.15

    # ── Intrinsic reward za odkrycie nowych kratek ────────────────────────
    # Soft decay zamiast binary cut: po zobaczeniu mgły kiedykolwiek bonus
    # spada z 0.03 do 0.01 (nie 0). Bot nadal motywowany do mapowania
    # nieznanego terenu w late game (np. żeby znaleźć drogę ucieczki),
    # ale exploration vs survival ma niższy priorytet niż w early game.
    exploration_scale = 0.01 if ctx.mist_ever_seen else 0.03
    reward += new_tiles * exploration_scale

    # ── Kara za MAINTAIN_DIST gdy broń nie korzysta z dystansu ──────────────
    # sword (zasięg 3) i axe (T-kształt, is_in_range obejmuje skosy) → OK.
    # bow → OK (już bez kary).
    # knife: przy dist 2-3 align zamiast podejścia → suboptymalne.
    # scroll: optimal=2 ale is_in_range sprawdza dist 1 → auto-atak nie odpali.
    if ctx.last_tactic == Tactic.MAINTAIN_DIST and ctx.last_weapon in ('knife', 'scroll'):
        reward -= 0.2

    return reward
