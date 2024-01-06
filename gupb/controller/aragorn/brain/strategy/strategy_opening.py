from gupb.model import characters

from gupb.controller.aragorn.constants import INFINITY

from .strategy import Strategy



class StrategyOpening(Strategy):
    def prepare_actions(self) -> characters.Action:
        yield self._prevent_idle_penalty()
        yield self._defend_from_attacks()
        yield self._pick_up_potion(5)
        yield self._pick_up_weapon(INFINITY)
        yield self._rotate_to_see_more()
        yield self._spin()
