"""
Prosty bot ze stubem sieci neuronowej.
Używa observation_parser do zamiany knowledge na wektor o stałym rozmiarze (INPUT_DIM)
oraz pamięci (np. zapamiętana pozycja menhiru). Na razie sieć zwraca zawsze DO_NOTHING.
"""

from __future__ import annotations

from typing import Optional

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

def network_predict(observation: list[float]) -> characters.Action:
    """
    Stub wywołania sieci neuronowej.
    observation: wektor o długości INPUT_DIM (z observation_parser.encode_observation).
    Tu później: model(observation) -> akcja.
    Na razie zawsze DO_NOTHING.
    """
    # TODO: np. action_id = model.predict(observation); return ACTIONS[action_id]
    assert len(observation) == INPUT_DIM
    return characters.Action.DO_NOTHING


class BIGbot(controller.Controller):
    """
    Bot sterowany (w przyszłości) siecią neuronową.
    - Parsuje knowledge na stały wektor (observation_parser).
    - Pamięta np. pozycję menhiru po pierwszym zobaczeniu i zawsze dodaje
      odległość/kąt do niego do wejścia sieci.
    """

    def __init__(self, bot_name: str = "BIGbot"):
        self.bot_name = bot_name
        self._menhir_position: Optional[coordinates.Coords] = None

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self._update_memory(knowledge)
        observation = observation_parser.encode_observation(
            knowledge, self._menhir_position
        )
        return network_predict(observation)

    def _update_memory(self, knowledge: characters.ChampionKnowledge) -> None:
        """Aktualizuje pamięć na podstawie widocznych pól (np. menhir)."""
        for coords, tile_desc in knowledge.visible_tiles.items():
            if tile_desc.type == "menhir":
                self._menhir_position = coords
                break

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._menhir_position = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BIGbot):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    @property
    def name(self) -> str:
        return f"BIGbot_{self.bot_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET


POTENTIAL_CONTROLLERS = [
    BIGbot("Stub"),
]
