from typing import Protocol

from gupb.model import characters

from ..state import CombatState


class CombatStrategy(Protocol):
    def search(self, state: CombatState) -> characters.Action | None: ...
