from __future__ import annotations

"""
BenjaminNetanyahu ma 3 gotowe tryby heurystyczne:
- `normal`
- `aggressive`
- `passive`

W wersji z inferencja bot korzysta z malej sieci (40 x 64 x 64 x 3).
Wagi sa zapisane w pliku `benjamin_weights.pt`.

W praktyce bot patrzy na aktualny stan gry, siec wybiera jeden z 3 trybow,
a wybrany tryb prowadzi postac przez kolejne 3 tury.
Potem wybor jest odswiezany ponownie.
"""

from enum import Enum
from typing import Callable, Optional

from gupb import controller
from gupb.controller.benjamin_netanyahu.aggressive_mode import BenjaminAggressiveMode
from gupb.controller.benjamin_netanyahu.normal_mode import BenjaminNormalMode
from gupb.controller.benjamin_netanyahu.passive_mode import BenjaminPassiveMode
from gupb.model import arenas
from gupb.model import characters

from .shared_state import BenjaminSharedState

MODE_HORIZON_TURNS = 3


class BenjaminMode(Enum):
    AGGRESSIVE = "aggressive"
    NORMAL = "normal"
    PASSIVE = "passive"


MODE_TO_INDEX = {
    BenjaminMode.NORMAL: 0,
    BenjaminMode.AGGRESSIVE: 1,
    BenjaminMode.PASSIVE: 2,
}
INDEX_TO_MODE = {value: key for key, value in MODE_TO_INDEX.items()}
ModeChoice = BenjaminMode | int
ModeSelector = Callable[[characters.ChampionKnowledge, BenjaminMode, int], ModeChoice]


class BenjaminNetanyahu(controller.Controller):
    def __init__(
            self,
            bot_name: str,
            mode_horizon_turns: int = MODE_HORIZON_TURNS,
            mode_selector: Optional[ModeSelector] = None,
            allow_oracle_menhir: bool = False,
    ) -> None:
        if mode_horizon_turns < 1:
            raise ValueError("mode_horizon_turns must be >= 1.")
        self.bot_name = bot_name
        self.mode_horizon_turns = int(mode_horizon_turns)
        self._mode_selector: Optional[ModeSelector] = mode_selector
        self.current_mode: BenjaminMode = BenjaminMode.NORMAL
        self._turns_left_in_mode: int = 0
        self._pending_mode: Optional[BenjaminMode] = None
        self._turns_taken: int = 0
        self._aggressive_expert, self._normal_expert, self._passive_expert = self._build_experts(
            bot_name=bot_name,
            allow_oracle_menhir=allow_oracle_menhir,
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BenjaminNetanyahu):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    @property
    def needs_mode_choice(self) -> bool:
        return self._turns_left_in_mode <= 0

    @property
    def turns_until_mode_change(self) -> int:
        return max(0, self._turns_left_in_mode)

    @property
    def turns_taken(self) -> int:
        return self._turns_taken

    @property
    def current_mode_index(self) -> int:
        return self.mode_to_index(self.current_mode)

    @property
    def shared_state(self) -> BenjaminSharedState:
        return self._normal_expert.shared_state

    def set_pending_mode(self, mode_choice: ModeChoice) -> None:
        self._pending_mode = self._normalise_mode_choice(mode_choice)

    def set_mode_selector(self, mode_selector: Optional[ModeSelector]) -> None:
        self._mode_selector = mode_selector

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.needs_mode_choice:
            self.current_mode = self._resolve_mode_choice(knowledge)
            self._turns_left_in_mode = self.mode_horizon_turns
        expert = self._expert_for_mode(self.current_mode)
        action = expert.decide(knowledge)
        self._turns_left_in_mode -= 1
        self._turns_taken += 1
        return action

    def praise(self, score: int) -> None:
        for expert in self._experts():
            expert.praise(score)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.current_mode = BenjaminMode.NORMAL
        self._turns_left_in_mode = 0
        self._pending_mode = None
        self._turns_taken = 0
        for expert in self._experts():
            expert.reset(game_no, arena_description)

    @staticmethod
    def _choose_mode(knowledge: characters.ChampionKnowledge) -> BenjaminMode:
        current_hp = BenjaminNetanyahu._current_hp(knowledge)
        starting_hp = characters.CHAMPION_STARTING_HP
        if current_hp > 0.7 * starting_hp:
            return BenjaminMode.AGGRESSIVE
        if current_hp < 0.3 * starting_hp:
            return BenjaminMode.PASSIVE
        return BenjaminMode.NORMAL

    @staticmethod
    def _current_hp(knowledge: characters.ChampionKnowledge) -> int:
        current_tile = knowledge.visible_tiles.get(knowledge.position)
        if current_tile is None or current_tile.character is None:
            return characters.CHAMPION_STARTING_HP
        return current_tile.character.health

    def _resolve_mode_choice(self, knowledge: characters.ChampionKnowledge) -> BenjaminMode:
        if self._pending_mode is not None:
            chosen_mode = self._pending_mode
            self._pending_mode = None
            return chosen_mode
        if self._mode_selector is not None:
            try:
                mode_choice = self._mode_selector(knowledge, self.current_mode, self._turns_taken)
                return self._normalise_mode_choice(mode_choice)
            except Exception:
                return self.current_mode
        return self._choose_mode(knowledge)

    @staticmethod
    def mode_to_index(mode: BenjaminMode) -> int:
        return MODE_TO_INDEX[mode]

    @staticmethod
    def mode_from_index(mode_index: int) -> BenjaminMode:
        index_value = int(mode_index)
        if index_value not in INDEX_TO_MODE:
            raise ValueError(f"Mode index out of range: {mode_index}.")
        return INDEX_TO_MODE[index_value]

    @staticmethod
    def _normalise_mode_choice(mode_choice: ModeChoice) -> BenjaminMode:
        if isinstance(mode_choice, BenjaminMode):
            return mode_choice
        return BenjaminNetanyahu.mode_from_index(int(mode_choice))

    def _expert_for_mode(self, mode: BenjaminMode) -> controller.Controller:
        if mode == BenjaminMode.AGGRESSIVE:
            return self._aggressive_expert
        if mode == BenjaminMode.PASSIVE:
            return self._passive_expert
        return self._normal_expert

    @staticmethod
    def _build_experts(
            bot_name: str,
            allow_oracle_menhir: bool,
    ) -> tuple[controller.Controller, controller.Controller, controller.Controller]:
        shared_state = BenjaminSharedState()
        return (
            BenjaminAggressiveMode(
                bot_name=bot_name,
                shared_state=shared_state,
                allow_oracle_menhir=allow_oracle_menhir,
            ),
            BenjaminNormalMode(
                bot_name=bot_name,
                shared_state=shared_state,
                allow_oracle_menhir=allow_oracle_menhir,
            ),
            BenjaminPassiveMode(
                bot_name=bot_name,
                shared_state=shared_state,
                allow_oracle_menhir=allow_oracle_menhir,
            ),
        )

    def _experts(self) -> tuple[controller.Controller, controller.Controller, controller.Controller]:
        return self._aggressive_expert, self._normal_expert, self._passive_expert

    @property
    def name(self) -> str:
        return self.bot_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BENJAMIN_NETANYAHU
