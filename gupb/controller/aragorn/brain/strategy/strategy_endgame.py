from gupb.model import characters

from .strategy import Strategy
from gupb.controller.aragorn.constants import INFINITY



class StrategyEndgame(Strategy):
    def prepare_actions(self) -> characters.Action:
        self._clear_variables()

        yield self._prevent_idle_penalty()
        yield self._defend_from_attacks()
        yield self._pick_up_potion(5)
        yield self._attack_in_range(INFINITY)
        yield self._conquer_menhir()
        yield self._pick_up_weapon(3)
        yield self._rotate_to_see_more()
        
        if self._brain.memory.position != self.menhirPos:
            yield self._explore_the_map()
        
        yield self._spin()
