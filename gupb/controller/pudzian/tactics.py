"""
Definicje mikro-taktyk dla DQN.

Wynesione z pudzian.py, żeby reward.py mógł importować Tactic bez
circular dependency (pudzian.py → reward.py → pudzian.py).
"""

from enum import IntEnum


class Tactic(IntEnum):
    """14 mikro-taktyk dostępnych dla sieci neuronowej."""
    # -- Walka i pozycjonowanie --
    APPROACH       = 0   # Szarżuj na najbliższego wroga
    ALIGN_AXIS     = 1   # Ustaw się na osi strzału z wrogiem
    MAINTAIN_DIST  = 2   # Utrzymuj optymalny dystans
    DODGE_LEFT     = 3   # Unik w lewo (prostopadle do wroga)
    DODGE_RIGHT    = 4   # Unik w prawo (prostopadle do wroga)
    FLEE_CLOSEST   = 5   # Uciekaj od najbliższego wroga

    # -- Eksploracja i przetrwanie --
    GET_POTION     = 6   # Idź po miksturę
    GET_WEAPON     = 7   # Idź po lepszą broń
    HOLD_MENHIR    = 8   # Trzymaj pozycję przy menhirze
    FOLLOW_MIST    = 9   # Podążaj za kompasem mgły (ucieczka od mgły)
    EXPLORE        = 10  # Idź w stronę nieodkrytych kratek
    SCAN           = 11  # Obróć się w miejscu (buduj mapę)

    # -- Surowe akcje pod kontrolą sieci (timing) --
    ATTACK         = 12  # Uderz teraz (naciągnięcie łuku / cios w zapamiętanego wroga / bait)
    WAIT           = 13  # Stój w miejscu (zasadzka / nie zdradzaj pozycji)


N_TACTICS = len(Tactic)
